package com.mumbai.domain

import kotlinx.datetime.LocalDate
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class BudgetTest {

    /** The real trip: Mon 10 to Sun 16 August 2026. */
    private val tripDays = (10..16).map { LocalDate(2026, 8, it) }
    private val day1 = tripDays[0]
    private val day3 = tripDays[2]
    private val budget = Paise.ofRupees(30_000)

    @Test
    fun `no budget means no projection at all`() {
        assertNull(
            projectBudget(null, listOf(DatedAmount(day1, Paise(14000))), tripDays, day1),
            "the caller must say 'no budget set' rather than render an invented denominator",
        )
    }

    @Test
    fun `nothing spent yet gives a per-day figure but refuses to project a run-out`() {
        val p = projectBudget(budget, emptyList(), tripDays, day1)
        assertNotNull(p)
        assertEquals(budget, p.remaining)
        assertEquals(7, p.daysRemaining)
        assertEquals(Paise(428571), p.perRemainingDay)          // 30,000 / 7 days
        assertNull(p.runsOutOn, "no rate exists yet, so extrapolating would be fabrication")
        assertEquals(0.0, p.fractionUsed)
    }

    @Test
    fun `remaining and today are computed from real expenses`() {
        val expenses = listOf(
            DatedAmount(day1, Paise(76800)),
            DatedAmount(day3, Paise(14000)),
            DatedAmount(day3, Paise(4000)),
        )
        val p = projectBudget(budget, expenses, tripDays, day3)
        assertNotNull(p)
        assertEquals(Paise(3_000_000 - 94_800), p.remaining)
        assertEquals(Paise(18000), p.spentToday)
        assertEquals(5, p.daysRemaining, "day 3 of 7 leaves 5 including today")
    }

    @Test
    fun `a sustainable rate produces no run-out warning`() {
        // ₹300 on day one, against ₹30,000 for a week. Nowhere near trouble.
        val p = projectBudget(budget, listOf(DatedAmount(day1, Paise(30000))), tripDays, day1)
        assertNotNull(p)
        assertNull(p.runsOutOn, "the money lasts the trip, so no alarm")
    }

    @Test
    fun `an unsustainable rate names the day the money runs out`() {
        // ₹12,000 on day one out of ₹30,000: that rate exhausts the budget inside the week.
        val p = projectBudget(budget, listOf(DatedAmount(day1, Paise(1_200_000))), tripDays, day1)
        assertNotNull(p)
        val out = p.runsOutOn
        assertNotNull(out, "spending 40% of the budget on day one must warn")
        assertTrue(out in tripDays, "the warning date must be inside the trip")
        assertEquals(LocalDate(2026, 8, 11), out, "₹18,000 left at ₹12,000/day runs out on day two")
    }

    @Test
    fun `the run-out date never falls outside the trip`() {
        for (rupees in listOf(4_000L, 6_000L, 9_000L, 12_000L, 20_000L, 29_000L)) {
            val p = projectBudget(
                budget, listOf(DatedAmount(day1, Paise.ofRupees(rupees))), tripDays, day1,
            )
            assertNotNull(p)
            p.runsOutOn?.let {
                assertTrue(it in tripDays, "₹$rupees/day projected outside the trip: $it")
            }
        }
    }

    @Test
    fun `going over budget is reported as over, not as a negative projection`() {
        val p = projectBudget(budget, listOf(DatedAmount(day1, Paise.ofRupees(31_000))), tripDays, day1)
        assertNotNull(p)
        assertTrue(p.isOver)
        assertEquals(Paise.ofRupees(1_000), p.overBy)
        assertNull(p.runsOutOn, "already over — there is nothing left to project")
        assertEquals(1.0, p.fractionUsed, "the meter clamps rather than overflowing")
    }

    @Test
    fun `outside the trip dates there is no per-day figure`() {
        val before = projectBudget(budget, emptyList(), tripDays, LocalDate(2026, 7, 31))
        assertNotNull(before)
        assertEquals(0, before.daysRemaining)
        assertNull(before.perRemainingDay)
        assertNull(before.runsOutOn)
    }

    @Test
    fun `the last day still counts as a day`() {
        val p = projectBudget(budget, emptyList(), tripDays, tripDays.last())
        assertNotNull(p)
        assertEquals(1, p.daysRemaining)
        assertEquals(budget, p.perRemainingDay)
    }

    @Test
    fun `the two real fares against a real budget`() {
        // Both ticket fares, as they would be if imported on day one.
        val p = projectBudget(
            budget,
            listOf(DatedAmount(day1, Paise(76800)), DatedAmount(day1, Paise(74300))),
            tripDays,
            day1,
        )
        assertNotNull(p)
        assertEquals(Paise(3_000_000 - 151_100), p.remaining)
        assertEquals("₹28,489", p.remaining.format())
    }

    @Test
    fun `fraction used is null for a zero budget rather than dividing by zero`() {
        val p = projectBudget(Paise.ZERO, listOf(DatedAmount(day1, Paise(100))), tripDays, day1)
        assertNotNull(p)
        assertNull(p.fractionUsed)
        assertTrue(p.isOver)
    }
}
