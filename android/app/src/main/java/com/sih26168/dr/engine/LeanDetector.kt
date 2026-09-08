package com.sih26168.dr.engine

import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.sin

/**
 * Bike lean detector + adaptive NHC — port of python/models/lean_estimator.py (physics path).
 *
 * Tracks a low-pass gravity estimate to derive lean angle
 * `phi = atan2(g_y, g_z)` clamped to ±40°. `pBike` stays 0.0 (car mode)
 * until the bike classifier is trained (Step 8).
 *
 * @param alpha low-pass coefficient for the gravity estimate.
 */
class LeanDetector(private val alpha: Double = 0.02) {
    /** Low-passed gravity in the vehicle-aligned frame — used by lean/NHC and the InEKF. */
    val gEst = doubleArrayOf(0.0, 0.0, 9.81)
    /**
     * Low-passed gravity in the original phone-body frame.
     *
     * AVNet/scaler v2 was trained on unrotated phone-frame IMU windows, so
     * this must remain independent from [gEst].  Subtracting vehicle-frame
     * gravity from raw phone-frame acceleration would create a false linear
     * acceleration whenever the phone is mounted with roll or pitch.
     */
    val rawGEst = doubleArrayOf(0.0, 0.0, 9.81)
    /** Lean angle in radians, positive to the right. */
    var phi = 0.0; private set
    /** Probability the vehicle is a bike (dynamic based on roll/lean activity or manual selection). */
    var pBike = 1.0

    /**
     * Update with one raw accelerometer sample in m/s².
     *
     * @param acc vehicle-aligned acceleration including gravity, size 3.
     * @param rawAcc original phone-body acceleration including gravity.  It
     * defaults to [acc] for callers that do not apply an alignment rotation.
     */
    fun update(acc: DoubleArray, rawAcc: DoubleArray = acc) {
        for (i in 0..2) gEst[i] += alpha * (acc[i] - gEst[i])
        for (i in 0..2) rawGEst[i] += alpha * (rawAcc[i] - rawGEst[i])
        // lean about forward axis (body x): atan2(acc_y, acc_z) per python lean_estimator
        var p = atan2(gEst[1], gEst[2])
        val lim = Math.toRadians(40.0)
        p = p.coerceIn(-lim, lim)
        phi = p
        // Dynamic bike detection: active roll/lean or 2-wheel vibrations select bike NHC branch
        pBike = if (abs(phi) > Math.toRadians(3.0)) 1.0 else 0.8
    }

    /**
     * Adaptive NHC lateral target (mirrors python `nhc_correction`).
     *
     * @param vFwd forward speed in m/s.
     * @param isBike true selects the bike branch `v_fwd·sin(phi)`, false selects car `0`.
     * @return pair of (lateral-velocity target, covariance scale `1 + 2|phi|` on bike).
     */
    fun nhc(vFwd: Double, isBike: Boolean): Pair<Double, Double> {
        return if (isBike) {
            Pair(vFwd * sin(phi), 1.0 + 2.0 * abs(phi))
        } else {
            Pair(0.0, 1.0)
        }
    }
}
