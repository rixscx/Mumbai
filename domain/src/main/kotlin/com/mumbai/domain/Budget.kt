package com.mumbai.domain

import kotlinx.datetime.LocalDate

/**
 * What the Fare Meter says. Every field is either derived from real numbers or null — there is no
 * "estimated" state that quietly fabricates a rate, because the meter's whole value is that you can
 * trust it before deciding whether to take the auto.
 */
data class BudgetProjection(
    /** Budget minus everything logged. Negative when over. */
    val remaining: Paise,
    /** Spent today, in the trip's zone. */
    val spentToday: Paise,
    /** What is left, divided across the days still to come including today. Null outside the trip. */
    val perRemainingDay: Paise?,
    /** Days left including today, or 0 outside the trip window. */
    val daysRemaining: Int,
    /** The day the money runs out at the current rate. Null when there is no rate to project from. */
    val runsOutOn: LocalDate?,
    /** Fraction of the budget consumed, 0..1, clamped. Null when no budget is set. */
    val fractionUsed: Double?,
) {
    val isOver: Boolean get() = remaining.isNegative
    val overBy: Paise? get() = if (isOver) -remaining else null
}

/** One expense, reduced to what budgeting needs. */
data class DatedAmount(val date: LocalDate, val amount: Paise)

/**
 * Project a budget over the trip.
 *
 * Deliberate refusals, each of which a naive version gets wrong:
 *  - with **no budget** there is no projection at all, and the caller must say so rather than
 *    render a meter with an invented denominator;
 *  - with **nothing spent yet** there is no rate, so [BudgetProjection.runsOutOn] stays null
 *    instead of extrapolating from zero;
 *  - **outside the trip dates** there are no remaining days, so no per-day figure is offered;
 *  - the run-out date is capped at the last day of the trip, because "you run out three days after
 *    you get home" is not information.
 */
fun projectBudget(
    budget: Paise?,
    expenses: List<DatedAmount>,
    tripDays: List<LocalDate>,
    today: LocalDate,
): BudgetProjection? {
    if (budget == null || tripDays.isEmpty()) return null

    val total = expenses.map { it.amount }.sum()
    val spentToday = expenses.filter { it.date == today }.map { it.amount }.sum()
    val remaining = budget - total

    val todayIndex = tripDays.indexOf(today)
    val daysRemaining = if (todayIndex < 0) 0 else tripDays.size - todayIndex
    val perDay = if (daysRemaining > 0) Paise(remaining.value / daysRemaining) else null

    // The rate uses days *elapsed so far including today*, not the whole trip: on day two a
    // traveller wants to know their actual burn, not an average diluted by days they have not had.
    val runsOutOn = if (todayIndex >= 0 && daysRemaining > 0 && !total.isZero && !remaining.isNegative) {
        val elapsed = todayIndex + 1
        val ratePerDay = total.value / elapsed
        if (ratePerDay <= 0) null else {
            val daysOfMoneyLeft = (remaining.value / ratePerDay).toInt()
            if (daysOfMoneyLeft >= daysRemaining) null            // it lasts the trip; no warning
            else tripDays[(todayIndex + daysOfMoneyLeft).coerceAtMost(tripDays.lastIndex)]
        }
    } else null

    val fraction = if (budget.value <= 0) null
    else (total.value.toDouble() / budget.value.toDouble()).coerceIn(0.0, 1.0)

    return BudgetProjection(
        remaining = remaining,
        spentToday = spentToday,
        perRemainingDay = perDay,
        daysRemaining = daysRemaining,
        runsOutOn = runsOutOn,
        fractionUsed = fraction,
    )
}
