package com.sih26168.dr.engine

/**
 * Stationary detection + ZUPT gate — port of python/utils/zupt.py.
 *
 * A sample is stationary when accel/gyro-norm variance over the sliding window
 * is low *and* the optional speed gate passes; the flag latches only after
 * [minDurationS] of persistence. Vehicle thresholds @100Hz;
 * ZUPT means v=0 with tight R when stationary.
 *
 * @param windowSize sliding-window length in samples (0.5s @100Hz by default).
 * @param accVarThresh accel-norm variance threshold in (m/s²)².
 * @param gyroVarThresh gyro-norm variance threshold in (rad/s)².
 * @param minDurationS persistence required before reporting stationary.
 * @param speedThresh vehicle-speed gate in m/s (checked when speed != null).
 */
class ZuptDetector(
    private val windowSize: Int = 50,          // 0.5s @100Hz
    private val accVarThresh: Double = 0.05,
    private val gyroVarThresh: Double = 0.01,
    private val minDurationS: Double = 0.3,
    private val speedThresh: Double = 0.5,
) {
    private val accNorms = ArrayDeque<Double>(windowSize)
    private val gyroNorms = ArrayDeque<Double>(windowSize)
    private var candidateStartS: Double? = null
    private var nowS = 0.0
    private var lastANorm = 9.80665
    /** Latest stationary decision. */
    var isStationary = false; private set
    /** Latest hand shake / phone handling detection decision. */
    var isHandShake = false; private set

    /**
     * Feed one raw IMU sample.
     *
     * @param aBody acceleration incl. gravity in m/s².
     * @param wBody angular rate in rad/s.
     * @param dt elapsed seconds since the previous sample.
     * @param speed AI forward speed in m/s, or null to skip the speed gate. Call at 100Hz.
     * @return current [isStationary].
     */
    fun update(aBody: DoubleArray, wBody: DoubleArray, dt: Double, speed: Double?): Boolean {
        nowS += dt
        val aNorm = LieGroup.norm(aBody)
        val wNorm = LieGroup.norm(wBody)
        val wRollPitch = kotlin.math.sqrt(wBody[0] * wBody[0] + wBody[1] * wBody[1])
        val dtEff = dt.coerceAtLeast(0.005)
        val accJerk = kotlin.math.abs(aNorm - lastANorm) / dtEff
        lastANorm = aNorm

        accNorms.addLast(aNorm)
        gyroNorms.addLast(wNorm)
        if (accNorms.size > windowSize) accNorms.removeFirst()
        if (gyroNorms.size > windowSize) gyroNorms.removeFirst()
        if (accNorms.size < windowSize) {
            isStationary = false
            isHandShake = false
            return false
        }
        val aVar = variance(accNorms)
        val wVar = variance(gyroNorms)

        // Hand shake / phone handling: high angular velocity norm (>0.65 rad/s ~ 37°/s),
        // high out-of-plane roll/pitch rotation (>0.45 rad/s), high 3D gyro variance (>0.08),
        // or extreme acceleration jerk (>25 m/s³).
        isHandShake = (wNorm > 0.65 || wRollPitch > 0.45 || wVar > 0.08 || accJerk > 25.0)

        val speedOk = speed == null || speed < speedThresh
        if ((aVar < accVarThresh && wVar < gyroVarThresh && speedOk) || isHandShake) {
            // Elvis both assigns and yields a non-null start — no `!!` needed.
            val start = candidateStartS ?: nowS.also { candidateStartS = it }
            isStationary = (nowS - start) >= minDurationS || isHandShake
        } else {
            candidateStartS = null
            isStationary = false
        }
        return isStationary
    }

    private fun variance(d: ArrayDeque<Double>): Double {
        var m = 0.0
        for (x in d) m += x
        m /= d.size
        var v = 0.0
        for (x in d) { val e = x - m; v += e * e }
        return v / d.size
    }
}
