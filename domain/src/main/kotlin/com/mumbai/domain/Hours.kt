package com.mumbai.domain

import kotlinx.datetime.DayOfWeek
import kotlinx.datetime.Instant
import kotlinx.datetime.LocalDate
import kotlinx.datetime.LocalTime
import kotlinx.datetime.TimeZone
import kotlinx.datetime.toLocalDateTime

/** One continuous span a place is open, on a day it is open at all. */
data class OpenWindow(val open: LocalTime, val close: LocalTime, val note: String? = null) {
    init {
        require(open < close) {
            "window $open-$close does not advance; overnight spans must be modelled as two windows"
        }
    }
}

/**
 * What is known about when a place is open — including, importantly, what is *not* known.
 *
 * [known] = false is a first-class state rather than an empty object, because the dataset's whole
 * discipline is that an unverified opening time ships empty instead of guessed. [opensAt] with no
 * closing time is likewise deliberate: half a fact is still a fact, and inventing the other half
 * to fill a window would be the exact failure this model exists to prevent.
 */
data class Hours(
    val known: Boolean,
    val alwaysOpen: Boolean = false,
    val windows: List<OpenWindow> = emptyList(),
    val opensAt: LocalTime? = null,
    val closedDays: Set<DayOfWeek> = emptySet(),
    val closedDaysVerified: Boolean = false,
    val note: String? = null,
) {
    init {
        if (!known) {
            require(windows.isEmpty() && opensAt == null) {
                "hours.known is false but hours data is present — contradictory"
            }
            require(!note.isNullOrBlank()) {
                "hours.known is false with no note explaining what is unknown"
            }
        }
    }

    companion object {
        /** A street, maidan or seafront: no gate, so no opening hour to cite. */
        fun alwaysOpen(note: String? = null) = Hours(known = true, alwaysOpen = true, note = note)

        fun unknown(note: String) = Hours(known = false, note = note)
    }
}

/** The answer to "can I walk in right now". */
sealed interface OpenState {
    /** Definitely open, with a closing time we actually know. */
    data class Open(val closesAt: LocalTime, val minutesLeft: Int, val note: String? = null) : OpenState

    /** Past a verified opening time, but the closing time was never sourced. */
    data class LikelyOpen(val since: LocalTime) : OpenState

    /** Shut. [opensAt] is the next opening today, when there is one. */
    data class Closed(val reason: ClosedReason, val opensAt: LocalTime? = null) : OpenState

    /** Hours were never verified, so no claim is made either way. */
    data object Unknown : OpenState

    val isOpenish: Boolean get() = this is Open || this is LikelyOpen
}

enum class ClosedReason {
    /** Shut for this whole weekday — the closure that wrecks a plan. */
    WEEKLY_CLOSURE,

    /** Open on this weekday, but not at this hour. */
    OUTSIDE_HOURS,
}

/** A weekday-long closure, surfaced separately because it is the day-planning question. */
data class AllDayClosure(val day: DayOfWeek, val verified: Boolean)

/**
 * Is this place shut for the whole of [day]?
 *
 * Deliberately distinct from [stateAt]. A dawn fish market evaluated at noon is *closed* but is
 * not *shut on Sunday*, and conflating the two produced a real bug: the day view told the traveller
 * the Dadar flower market was closed on Monday when in fact it runs 04:30–07:30 every morning.
 */
fun Hours.closedAllDay(day: DayOfWeek): AllDayClosure? {
    if (!known || alwaysOpen) return null
    if (day !in closedDays) return null
    return AllDayClosure(day, closedDaysVerified)
}

/**
 * Resolve [Hours] against a real instant, in the *trip's* zone.
 *
 * [zone] is a required parameter with no default on purpose. The device's zone must never own the
 * day boundary — a traveller whose phone is still on IST-minus-something would otherwise be told a
 * museum is open on the wrong day. See docs/TRIP.md, where an IRCTC ticket printed at 01:44 IST
 * demonstrated this bug class in the first real document the project touched.
 */
fun Hours.stateAt(instant: Instant, zone: TimeZone): OpenState {
    if (!known) return OpenState.Unknown
    if (alwaysOpen) return OpenState.Open(closesAt = LocalTime(23, 59), minutesLeft = Int.MAX_VALUE)

    val local = instant.toLocalDateTime(zone)
    return stateAt(local.date.dayOfWeek, local.time)
}

/** The pure, testable core: a weekday and a wall-clock time, no zone arithmetic left to do. */
fun Hours.stateAt(day: DayOfWeek, time: LocalTime): OpenState {
    if (!known) return OpenState.Unknown
    if (alwaysOpen) return OpenState.Open(closesAt = LocalTime(23, 59), minutesLeft = Int.MAX_VALUE)
    if (day in closedDays) return OpenState.Closed(ClosedReason.WEEKLY_CLOSURE)

    val now = time.minuteOfDay

    if (windows.isNotEmpty()) {
        windows.firstOrNull { now >= it.open.minuteOfDay && now < it.close.minuteOfDay }
            ?.let { return OpenState.Open(it.close, it.close.minuteOfDay - now, it.note) }
        val next = windows.map { it.open }.filter { it.minuteOfDay > now }.minByOrNull { it.minuteOfDay }
        return OpenState.Closed(ClosedReason.OUTSIDE_HOURS, next)
    }

    opensAt?.let { open ->
        return if (now >= open.minuteOfDay) OpenState.LikelyOpen(open)
        else OpenState.Closed(ClosedReason.OUTSIDE_HOURS, open)
    }

    return OpenState.Unknown
}

/** Which of [days] this place is shut for entirely — the list a traveller needs before booking. */
fun Hours.allDayClosuresAcross(days: Iterable<LocalDate>): List<AllDayClosure> =
    days.mapNotNull { closedAllDay(it.dayOfWeek) }.distinctBy { it.day }

internal val LocalTime.minuteOfDay: Int get() = hour * 60 + minute
