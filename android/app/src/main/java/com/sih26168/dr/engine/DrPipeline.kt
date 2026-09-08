package com.sih26168.dr.engine

import android.content.Context
import com.sih26168.dr.map.HmmMapMatcher
import com.sih26168.dr.map.RoadGraph
import kotlin.math.max

/**
 * Glues the full engine: AVNet inference -> InEKF (NHC/ZUPT) -> map matcher.
 * Called from MainActivity's 100Hz sensor loop (denormalize -> push) and
 * 10Hz fusion tick (predict -> update -> emit pose).
 */
class DrPipeline(context: Context, useGravity: Boolean = true) {

    init {
        // P2 refuse-to-run: a scaler/model pair from a mismatched window spec
        // throws here — silent degraded inference is worse than a crash with
        // a clear message. (Scaler's own init also verifies the fingerprint.)
        WindowSpecGuard.verifyScaler(context)
    }

    val scaler = Scaler(context)
    val avnet = AVNetInference(context)
    val lean = LeanDetector()
    val zupt = ZuptDetector()
    val ekf = InEKFEngine(useGravity = false)   // we feed gravity-removed linear acc; engine must NOT add G again
    val alignment = AlignmentEngine()
    val seamless = SeamlessHandler()

    private var roadGraph: RoadGraph? = null
    private var matcher: HmmMapMatcher? = null

    /** Current fusion state (sealed — consume with exhaustive `when`). */
    var mode: SeamlessHandler.FusionMode = SeamlessHandler.FusionMode.GnssAided(trust = 1.0)
        private set
    var lat = 0.0
    var lon = 0.0
    var lastSnappedLat = 0.0
    var lastSnappedLon = 0.0
    var lastV = 0.0; private set
    /** Debug — raw model output (before gates) and last stationary decision. */
    var lastRawModelV = 0.0; private set
    var lastStill = false; private set
    val motionConfirmMsPublic: Int get() = motionConfirmMs.toInt()
    /** Rate-limited + debounced forward speed used for DR. Exposed for UI/position. */
    val smoothedV: Double get() = velSmooth

    companion object {
        const val ZUPT_HOLD_MS = 800.0             // hold v=0 this long after a still-gate fires
        const val MOTION_CONFIRM_MS = 250.0        // sustained un-gated motion before trusting model
        const val V_DEADBAND = 0.15                // m/s — below this, don't move position (walking ~0.8+)
        const val V_STEP_LIMIT = 0.5               // max |Δv| per 0.1s tick (~5 m/s^2)
        const val V_SMOOTH_ALPH = 0.25             // ~0.35s low-pass at 10Hz
        // GNSS sanity gate: GPS ground-speed below this (m/s) means we are NOT moving —
        // overrides AI speed. Margin 0.3 covers GPS noise (~0.1-0.2 m/s) + walking start-up.
        const val GNSS_STILL_SPEED = 0.3
        // Latched gate: once GPS says still, AI speed stays blocked until GPS itself says
        // moving (or this max hold expires — guards against a stale gate after GPS dies).
        // Indoor GPS flaps INS<->GNSS every ~1.5s; a short timer hold leaked through every
        // flap (34m fake distance measured). Latch + explicit clear is flap-proof.
        const val GNSS_STILL_MAX_HOLD_MS = 30_000.0
    }
    private var velSmooth = 0.0
    private var lastModelV = 0.0
    private var motionConfirmMs = 0.0
    private var zuptHoldMsRem = 0.0
    private var gnssStillLatched = false
    private var gnssStillDeadlineMs = 0.0
    /** Engine clock (s), advanced in [onImu] — same base used for gate deadlines. */
    private var engineS = 0.0

    /** Wire the offline road graph when available (bundled asset or extracted). */
    fun setRoadGraph(g: RoadGraph?) {
        roadGraph = g
        matcher = g?.let { HmmMapMatcher(it) }
    }

    /** Called from the GNSS callback: GPS ground speed (m/s) says we are standing still. */
    fun onGnssStill() {
        gnssStillLatched = true
        gnssStillDeadlineMs = engineS * 1000.0 + GNSS_STILL_MAX_HOLD_MS
    }

    /** Called from the GNSS callback: GPS reports real movement — clear the still latch. */
    fun onGnssMoving() {
        gnssStillLatched = false
    }

    var refLat = 0.0
    var refLon = 0.0
    private var refSet = false

    /** Called when a live GNSS fix arrives — fuses position into InEKF with scaled covariance. */
    fun onGnssFix(fixLat: Double, fixLon: Double, accuracyMeters: Double) {
        val nowMs = (engineS * 1000.0).toLong()
        seamless.onFix(nowMs)
        if (!refSet) {
            refLat = fixLat
            refLon = fixLon
            refSet = true
        }
        val pN = (fixLat - refLat) * 111139.0
        val pE = (fixLon - refLon) * (111139.0 * kotlin.math.cos(Math.toRadians(refLat)))
        val rScale = seamless.gnssRScale()
        val rVar = (accuracyMeters * accuracyMeters).coerceAtLeast(1.0) * rScale
        ekf.updatePosition(doubleArrayOf(pN, pE, 0.0), doubleArrayOf(rVar, rVar, 25.0 * rScale))
        updateLatLonFromEkf()
    }

    private fun updateLatLonFromEkf() {
        if (!refSet) return
        val pos = ekf.position() // [pN, pE, pUp]
        lat = refLat + pos[0] / 111139.0
        val cosLat = kotlin.math.cos(Math.toRadians(refLat)).coerceAtLeast(1e-6)
        lon = refLon + pos[1] / (111139.0 * cosLat)
    }

    /** One raw IMU sample (acc m/s^2 incl. gravity, gyro rad/s) @100Hz. */
    fun onImu(acc: DoubleArray, gyro: DoubleArray, dt: Double) {
        engineS += dt
        alignment.updateAccel(acc)
        // Rotate raw IMU into vehicle-aligned coordinates using roll/pitch for EKF & dynamics
        val (accVeh, gyroVeh) = alignment.alignImu(acc, gyro)
        alignment.updateGyro(gyroVeh[2], dt)
        // Maintain gravity estimates in both frames: the InEKF consumes
        // vehicle-aligned data, while AVNet must retain its trained raw-phone
        // input convention (see WINDOW_SPEC v2).
        lean.update(accVeh, rawAcc = acc)

        // CRITICAL (P0 contract): model was trained on UNROTATED gravity-removed linear acc + raw body gyro.
        val rawG = lean.rawGEst
        val linAccRaw = doubleArrayOf(acc[0] - rawG[0], acc[1] - rawG[1], acc[2] - rawG[2])
        val norm = FloatArray(6)
        scaler.normalize(
            floatArrayOf(linAccRaw[0].toFloat(), linAccRaw[1].toFloat(), linAccRaw[2].toFloat(),
                gyro[0].toFloat(), gyro[1].toFloat(), gyro[2].toFloat()),
            norm,
        )

        val vehicleG = lean.gEst
        val linAccVeh = doubleArrayOf(
            accVeh[0] - vehicleG[0],
            accVeh[1] - vehicleG[1],
            accVeh[2] - vehicleG[2],
        )
        // 100 Hz ZUPT stationary detection on every IMU sample
        val still = zupt.update(accVeh, gyroVeh, dt, null)
        lastStill = still

        // 100 Hz InEKF state propagation on every IMU sample (only when moving)
        if (!still) {
            ekf.propagate(gyroVeh, linAccVeh, dt)
            updateLatLonFromEkf()
        }

        if (avnet.push(norm)) {
            val rawV = max(avnet.vPred.toDouble(), 0.0)
            lastRawModelV = rawV

            // Motion confirmation: model must report speed above deadband for a few
            // consecutive ticks before trusting it (kills table nudges & spikes).
            if (still || rawV < V_DEADBAND) {
                motionConfirmMs = 0.0
                if (still) zuptHoldMsRem = ZUPT_HOLD_MS
            } else if (motionConfirmMs < MOTION_CONFIRM_MS) {
                motionConfirmMs += 100.0
            }
            val gnssGateActive = gnssStillLatched && engineS * 1000.0 < gnssStillDeadlineMs
            if (gnssGateActive) motionConfirmMs = 0.0
            if (!gnssGateActive) gnssStillLatched = false
            val trustModel = motionConfirmMs >= MOTION_CONFIRM_MS && zuptHoldMsRem <= 0.0 && !gnssGateActive

            val vSourced = if (trustModel) rawV else 0.0

            // Rate-limit: no 0 -> 10 m/s inside 100ms.
            val step = (vSourced - lastModelV).coerceIn(-V_STEP_LIMIT, V_STEP_LIMIT)
            lastModelV += step

            // Low-pass to kill remaining transients.
            velSmooth += V_SMOOTH_ALPH * (lastModelV - velSmooth)

            if (zuptHoldMsRem > 0.0) zuptHoldMsRem -= 100.0

            val v = if (velSmooth > V_DEADBAND) velSmooth else 0.0
            val vLatRaw = lean.nhc(v, lean.pBike > 0.5).first
            val moving = v > 0.0
            val rFwd = if (!moving) 0.05 * 0.05 else max(avnet.sigmaV.toDouble(), 0.3).let { it * it }

            val z = doubleArrayOf(v, vLatRaw, 0.0)
            val r = doubleArrayOf(rFwd, rFwd, 25.0)
            ekf.updateVelocity(z, r)
            lastV = v
        }
    }

    /** 10Hz fusion tick: propagate + velocity/NHC/ZUPT update. Returns v_fwd (ZUPT-corrected). */
    fun onFusionTick(dt: Double, gnssSpeed: Double?, gnssCourseRad: Double?): Double {
        mode = seamless.tick((dt * 1000).toInt())
        if (mode is SeamlessHandler.FusionMode.DeadReckoning) {
            alignment.onGnssLost()
        }
        gnssCourseRad?.let { gnssSpeed?.let { s -> alignment.updateGnssHeading(it, s) } }
        return lastV
    }

    /** After ekf.updateVelocity, call to emit pose + map snap. */
    fun emitPose(gnssLat: Double?, gnssLon: Double?): Pair<Double, Double> {
        matcher?.let { m ->
            // Matcher expects heading in radians
            val fix = m.update(lat, lon, alignment.currentYaw)
            if (fix != null) { lastSnappedLat = fix.lat; lastSnappedLon = fix.lon }
        }
        return Pair(lat, lon)
    }
}
