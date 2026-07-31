package com.mumbai.domain

import kotlinx.datetime.DayOfWeek
import kotlinx.datetime.Instant
import kotlinx.datetime.LocalDate
import kotlinx.datetime.LocalTime
import kotlinx.datetime.TimeZone
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * These fixtures are the real entries from data/places.mumbai.json, not invented examples. If the
 * dataset's hours change, these tests should be updated to match it — they are the executable
 * statement of what the curated data currently claims.
 */
class HoursTest {

    private val mumbai = TimeZone.of("Asia/Kolkata")

    /** Britannia & Co: lunch only, 11:30–16:00, closed Sunday. */
    private val britannia = Hours(
        known = true,
        windows = listOf(OpenWindow(LocalTime(11, 30), LocalTime(16, 0), "Lunch service only.")),
        closedDays = setOf(DayOfWeek.SUNDAY),
        closedDaysVerified = true,
    )

    /** Asthika Samaj: 05:00–12:00 and 16:30–21:00 — two windows, a gap in the middle. */
    private val asthikaSamaj = Hours(
        known = true,
        windows = listOf(
            OpenWindow(LocalTime(5, 0), LocalTime(12, 0)),
            OpenWindow(LocalTime(16, 30), LocalTime(21, 0)),
        ),
    )

    /** Yazdani Bakery: opens 07:00, closing time never sourced. */
    private val yazdani = Hours(known = true, opensAt = LocalTime(7, 0))

    /** Marine Drive: a public seafront. No gate, so no opening hour to cite. */
    private val marineDrive = Hours.alwaysOpen("Public seafront with no gate.")

    /** David Sassoon Library: hours genuinely unverified. */
    private val sassoon = Hours.unknown("Opening hours are NOT verified; sources say to ring ahead.")

    /** Dr Bhau Daji Lad: 10:00–17:30, closed Wednesdays. */
    private val bhauDajiLad = Hours(
        known = true,
        windows = listOf(OpenWindow(LocalTime(10, 0), LocalTime(17, 30))),
        closedDays = setOf(DayOfWeek.WEDNESDAY),
        closedDaysVerified = true,
    )

    /** Dadar flower market: 04:30–07:30, every day. The regression fixture. */
    private val flowerMarket = Hours(
        known = true,
        windows = listOf(OpenWindow(LocalTime(4, 30), LocalTime(7, 30))),
    )

    // ------------------------------------------------------------------ windows

    @Test
    fun `inside a window is open, with the real closing time`() {
        val st = britannia.stateAt(DayOfWeek.TUESDAY, LocalTime(12, 0))
        assertIs<OpenState.Open>(st)
        assertEquals(LocalTime(16, 0), st.closesAt)
        assertEquals(240, st.minutesLeft)
    }

    @Test
    fun `closing soon is derivable from minutesLeft`() {
        val st = britannia.stateAt(DayOfWeek.TUESDAY, LocalTime(15, 20))
        assertIs<OpenState.Open>(st)
        assertEquals(40, st.minutesLeft)
        assertTrue(st.minutesLeft <= 60, "the UI keys 'closing soon' off this")
    }

    @Test
    fun `after closing is outside hours, not a weekly closure`() {
        val st = britannia.stateAt(DayOfWeek.TUESDAY, LocalTime(18, 0))
        assertIs<OpenState.Closed>(st)
        assertEquals(ClosedReason.OUTSIDE_HOURS, st.reason)
        assertNull(st.opensAt, "nothing else opens later today")
    }

    @Test
    fun `before opening reports when it opens`() {
        val st = britannia.stateAt(DayOfWeek.TUESDAY, LocalTime(9, 0))
        assertIs<OpenState.Closed>(st)
        assertEquals(LocalTime(11, 30), st.opensAt)
    }

    @Test
    fun `the gap between two windows points at the next one`() {
        assertIs<OpenState.Open>(asthikaSamaj.stateAt(DayOfWeek.MONDAY, LocalTime(6, 0)))
        val gap = asthikaSamaj.stateAt(DayOfWeek.MONDAY, LocalTime(14, 0))
        assertIs<OpenState.Closed>(gap)
        assertEquals(LocalTime(16, 30), gap.opensAt, "should point at the evening darshan")
        assertIs<OpenState.Open>(asthikaSamaj.stateAt(DayOfWeek.MONDAY, LocalTime(17, 0)))
    }

    @Test
    fun `boundaries are half-open so a closing minute is not open`() {
        assertIs<OpenState.Open>(britannia.stateAt(DayOfWeek.TUESDAY, LocalTime(11, 30)))
        assertIs<OpenState.Closed>(britannia.stateAt(DayOfWeek.TUESDAY, LocalTime(16, 0)))
    }

    // ------------------------------------------------- partial and absent knowledge

    @Test
    fun `a verified opening with no closing time is only likely open`() {
        assertIs<OpenState.LikelyOpen>(yazdani.stateAt(DayOfWeek.TUESDAY, LocalTime(8, 0)))
        assertIs<OpenState.LikelyOpen>(yazdani.stateAt(DayOfWeek.TUESDAY, LocalTime(23, 30)))
        val early = yazdani.stateAt(DayOfWeek.TUESDAY, LocalTime(6, 0))
        assertIs<OpenState.Closed>(early)
        assertEquals(LocalTime(7, 0), early.opensAt)
    }

    @Test
    fun `always open needs no citation and never closes`() {
        assertTrue(marineDrive.stateAt(DayOfWeek.TUESDAY, LocalTime(3, 0)).isOpenish)
        assertTrue(marineDrive.stateAt(DayOfWeek.SUNDAY, LocalTime(23, 59)).isOpenish)
    }

    @Test
    fun `unverified hours make no claim in either direction`() {
        assertEquals(OpenState.Unknown, sassoon.stateAt(DayOfWeek.TUESDAY, LocalTime(12, 0)))
        assertFalse(sassoon.stateAt(DayOfWeek.TUESDAY, LocalTime(12, 0)).isOpenish)
    }

    @Test
    fun `hours known false with data is rejected at construction`() {
        val e = runCatching {
            Hours(known = false, opensAt = LocalTime(7, 0), note = "x")
        }.exceptionOrNull()
        assertNotNull(e, "contradictory hours must not be constructible")
    }

    @Test
    fun `hours known false with no note is rejected`() {
        assertNotNull(runCatching { Hours(known = false) }.exceptionOrNull())
    }

    @Test
    fun `a window that does not advance is rejected`() {
        assertNotNull(
            runCatching { OpenWindow(LocalTime(22, 0), LocalTime(2, 0)) }.exceptionOrNull(),
            "overnight spans must be two windows, not one that wraps",
        )
    }

    // ------------------------------------------- all-day closure vs outside hours

    @Test
    fun `weekly closure is reported distinctly from being outside hours`() {
        val sunday = britannia.stateAt(DayOfWeek.SUNDAY, LocalTime(12, 0))
        assertIs<OpenState.Closed>(sunday)
        assertEquals(ClosedReason.WEEKLY_CLOSURE, sunday.reason)
    }

    @Test
    fun `a dawn market is not shut for the day just because you asked at noon`() {
        // The regression. Evaluated at midday the flower market is closed, but it is open every
        // single morning, so a day-planning view must not strike it out.
        val atNoon = flowerMarket.stateAt(DayOfWeek.MONDAY, LocalTime(12, 0))
        assertIs<OpenState.Closed>(atNoon)
        assertEquals(ClosedReason.OUTSIDE_HOURS, atNoon.reason)
        assertNull(flowerMarket.closedAllDay(DayOfWeek.MONDAY), "not a weekly closure")
        assertTrue(flowerMarket.stateAt(DayOfWeek.MONDAY, LocalTime(6, 0)).isOpenish)
    }

    @Test
    fun `all day closure carries whether it was verified`() {
        val c = britannia.closedAllDay(DayOfWeek.SUNDAY)
        assertNotNull(c)
        assertEquals(DayOfWeek.SUNDAY, c.day)
        assertTrue(c.verified)

        val unverified = britannia.copy(closedDaysVerified = false)
        assertEquals(false, unverified.closedAllDay(DayOfWeek.SUNDAY)?.verified)
    }

    @Test
    fun `always open and unknown are never all-day closed`() {
        DayOfWeek.entries.forEach {
            assertNull(marineDrive.closedAllDay(it))
            assertNull(sassoon.closedAllDay(it))
        }
    }

    // --------------------------------------------------- the trip's real days

    @Test
    fun `the museum closure lands on Wednesday 12 August, inside the trip`() {
        val tripDays = (10..16).map { LocalDate(2026, 8, it) }
        val closures = bhauDajiLad.allDayClosuresAcross(tripDays)
        assertEquals(1, closures.size)
        assertEquals(DayOfWeek.WEDNESDAY, closures.single().day)
        assertEquals(
            DayOfWeek.WEDNESDAY,
            tripDays.single { bhauDajiLad.closedAllDay(it.dayOfWeek) != null }.dayOfWeek,
        )
    }

    @Test
    fun `both bookend days of the trip are Mondays`() {
        assertEquals(DayOfWeek.MONDAY, LocalDate(2026, 8, 10).dayOfWeek)
        assertEquals(DayOfWeek.MONDAY, LocalDate(2026, 8, 17).dayOfWeek)
    }

    // ---------------------------------------------------------- zone handling

    @Test
    fun `the trip zone owns the day boundary, not the device`() {
        // 2026-08-11T19:00Z is 00:30 on the 12th in Mumbai. A place shut on Wednesdays must read
        // as shut, even though the instant is still Tuesday in UTC.
        val instant = Instant.parse("2026-08-11T19:00:00Z")
        val inMumbai = bhauDajiLad.stateAt(instant, mumbai)
        val inUtc = bhauDajiLad.stateAt(instant, TimeZone.UTC)

        assertIs<OpenState.Closed>(inMumbai)
        assertEquals(ClosedReason.WEEKLY_CLOSURE, inMumbai.reason, "Wednesday in Mumbai")

        assertIs<OpenState.Closed>(inUtc)
        assertEquals(ClosedReason.OUTSIDE_HOURS, inUtc.reason, "still Tuesday night in UTC")
    }

    @Test
    fun `midday IST resolves inside the lunch window regardless of caller zone`() {
        val noonIst = Instant.parse("2026-08-11T06:30:00Z")   // 12:00 IST
        assertIs<OpenState.Open>(britannia.stateAt(noonIst, mumbai))
    }
}
