package com.mumbai.data

import android.content.Context
import com.mumbai.domain.Hours
import com.mumbai.domain.OpenWindow
import com.mumbai.domain.Paise
import kotlinx.datetime.DayOfWeek
import kotlinx.datetime.LocalTime
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * The curated dataset, read from assets.
 *
 * These DTOs mirror data/schema/place.schema.json exactly and do nothing clever. The mapping into
 * [Hours] is where the interesting work happens, and it is deliberately lossy in one direction
 * only: an unparseable time becomes "not known" rather than a default, because a default opening
 * hour is a fabricated fact and the whole dataset exists to avoid those.
 */
@Serializable
data class PlacesFile(
    val version: Int = 1,
    val generated: String = "",
    val places: List<PlaceDto> = emptyList(),
)

@Serializable
data class PlaceDto(
    val id: String,
    val name: String,
    @SerialName("name_local") val nameLocal: String? = null,
    val cluster: String,
    val type: List<String> = emptyList(),
    @SerialName("what_it_is") val whatItIs: String = "",
    @SerialName("why_locals_rate_it") val whyLocalsRateIt: String = "",
    @SerialName("insider_rules") val insiderRules: List<String> = emptyList(),
    val hours: HoursDto = HoursDto(known = false, note = "missing from the dataset"),
    val cost: CostDto = CostDto(),
    @SerialName("how_to_get_there") val howToGetThere: TransitDto = TransitDto(),
    @SerialName("monsoon_safe") val monsoonSafe: String = "conditional",
    @SerialName("monsoon_note") val monsoonNote: String? = null,
    @SerialName("safety_notes") val safetyNotes: String = "",
    val accessibility: String = "",
    val confidence: String = "medium",
    @SerialName("confidence_note") val confidenceNote: String? = null,
    val sources: List<SourceDto> = emptyList(),
    @SerialName("last_reviewed") val lastReviewed: String = "",
)

@Serializable
data class HoursDto(
    val known: Boolean,
    @SerialName("always_open") val alwaysOpen: Boolean = false,
    val windows: List<WindowDto> = emptyList(),
    @SerialName("opens_at") val opensAt: String? = null,
    @SerialName("closed_days") val closedDays: List<String> = emptyList(),
    @SerialName("closed_days_verified") val closedDaysVerified: Boolean = false,
    val note: String? = null,
)

@Serializable
data class WindowDto(val open: String, val close: String, val note: String? = null)

@Serializable
data class CostDto(
    @SerialName("avg_paise") val avgPaise: Long? = null,
    val band: String = "unknown",
    @SerialName("cash_only") val cashOnly: Boolean? = null,
    val note: String? = null,
)

@Serializable
data class TransitDto(
    @SerialName("nearest_station") val nearestStation: String? = null,
    val line: String? = null,
    @SerialName("walk_minutes") val walkMinutes: Int? = null,
    val note: String? = null,
)

@Serializable
data class SourceDto(val url: String, val retrieved: String = "", val supports: List<String> = emptyList())

/** A place with its hours already mapped into the domain model. */
data class Place(
    val dto: PlaceDto,
    val hours: Hours,
) {
    val id get() = dto.id
    val name get() = dto.name
    val cluster get() = dto.cluster
    val cost: Paise? get() = dto.cost.avgPaise?.let { Paise(it) }
}

private val json = Json { ignoreUnknownKeys = true; isLenient = false }

private fun parseTime(raw: String?): LocalTime? =
    raw?.let { runCatching { LocalTime.parse(it) }.getOrNull() }

private fun parseDay(raw: String): DayOfWeek? = when (raw.lowercase()) {
    "mon" -> DayOfWeek.MONDAY
    "tue" -> DayOfWeek.TUESDAY
    "wed" -> DayOfWeek.WEDNESDAY
    "thu" -> DayOfWeek.THURSDAY
    "fri" -> DayOfWeek.FRIDAY
    "sat" -> DayOfWeek.SATURDAY
    "sun" -> DayOfWeek.SUNDAY
    else -> null
}

/**
 * Map the JSON shape onto [Hours].
 *
 * Anything malformed collapses to `known = false` with a note naming the problem. That is the
 * conservative direction: the app then says "hours not verified" instead of asserting a time it
 * invented, which is the only acceptable failure mode for this field.
 */
fun HoursDto.toDomain(placeId: String): Hours {
    val closed = closedDays.mapNotNull(::parseDay).toSet()

    if (!known) {
        return Hours.unknown(note ?: "Hours were not verified for $placeId.")
    }
    if (alwaysOpen) {
        return Hours(known = true, alwaysOpen = true, closedDays = closed, note = note)
    }

    val mapped = windows.mapNotNull { w ->
        val o = parseTime(w.open)
        val c = parseTime(w.close)
        if (o == null || c == null || o >= c) null else OpenWindow(o, c, w.note)
    }
    if (mapped.isNotEmpty()) {
        return Hours(
            known = true,
            windows = mapped,
            closedDays = closed,
            closedDaysVerified = closedDaysVerified,
            note = note,
        )
    }

    parseTime(opensAt)?.let {
        return Hours(
            known = true,
            opensAt = it,
            closedDays = closed,
            closedDaysVerified = closedDaysVerified,
            note = note,
        )
    }

    return Hours.unknown(
        note ?: "Hours for $placeId could not be read from the dataset, so none are claimed.",
    )
}

object Dataset {
    /** Loaded once; the whole dataset is ~110 KB, so there is nothing to stream or page. */
    fun load(context: Context): List<Place> {
        val text = context.assets.open("places.json").bufferedReader().use { it.readText() }
        return json.decodeFromString<PlacesFile>(text).places
            .map { Place(it, it.hours.toDomain(it.id)) }
    }
}
