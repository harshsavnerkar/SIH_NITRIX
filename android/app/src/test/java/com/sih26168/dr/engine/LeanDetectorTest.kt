package com.sih26168.dr.engine

import org.junit.Assert.assertEquals
import org.junit.Test
import kotlin.math.PI
import kotlin.math.sin

class LeanDetectorTest {

    @Test
    fun bikeLean30deg_vLatIsHalfForward() {
        // mirrors python/inekf_harness.py --test-lean (PASS case)
        val lean = LeanDetector(alpha = 1.0)  // instant low-pass
        // craft acc so atan2(acc_y, acc_z) = 30deg
        val g = 9.81
        val phi = Math.toRadians(30.0)
        lean.update(doubleArrayOf(0.0, g * sin(phi), g * kotlin.math.cos(phi)))
        val (vLat, rScale) = lean.nhc(5.0, isBike = true)
        assertEquals(5.0 * sin(phi), vLat, 1e-9)
        assertEquals(1.0 + 2.0 * phi, rScale, 1e-9)
    }

    @Test
    fun carFallback_zeroLateral() {
        val lean = LeanDetector()
        val (vLat, rScale) = lean.nhc(5.0, isBike = false)
        assertEquals(0.0, vLat, 1e-12)
        assertEquals(1.0, rScale, 1e-12)
    }

    @Test
    fun rawGravityStaysInPhoneFrameWhenVehicleFrameIsAligned() {
        val lean = LeanDetector(alpha = 1.0)
        // A phone rolled 30° sees gravity in Y/Z, while the alignment module
        // presents the same stationary sample as [0, 0, g] to the InEKF.
        val g = 9.81
        val roll = Math.toRadians(30.0)
        val raw = doubleArrayOf(0.0, g * sin(roll), g * kotlin.math.cos(roll))
        val vehicle = doubleArrayOf(0.0, 0.0, g)

        lean.update(vehicle, raw)

        for (i in 0..2) {
            assertEquals("raw gravity channel $i", raw[i], lean.rawGEst[i], 1e-12)
            assertEquals("vehicle gravity channel $i", vehicle[i], lean.gEst[i], 1e-12)
        }
    }
}
