package com.mumbai.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.mumbai.data.Place
import com.mumbai.domain.ClosedReason
import com.mumbai.domain.OpenState
import com.mumbai.domain.stateAt
import kotlinx.datetime.Clock
import kotlinx.datetime.TimeZone

/** The trip's zone. It, not the device's zone, owns the day boundary — see :domain's Hours doc. */
private val MUMBAI = TimeZone.of("Asia/Kolkata")

@Composable
fun PlacesScreen(places: List<Place>, onOpen: (Place) -> Unit) {
    // Evaluated once per composition rather than per row, so every row agrees on "now".
    val now = remember { Clock.System.now() }
    val states = remember(places) { places.associate { it.id to it.hours.stateAt(now, MUMBAI) } }
    val openCount = states.values.count { it.isOpenish }
    val byCluster = remember(places) { places.groupBy { it.cluster }.toSortedMap() }

    Scaffold { inner ->
        LazyColumn(
            modifier = Modifier.padding(inner),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp),
        ) {
            item {
                Column(Modifier.padding(16.dp, 12.dp, 16.dp, 4.dp)) {
                    Text("Places", style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.Bold)
                    Text(
                        "$openCount of ${places.size} open right now, Mumbai time",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.height(8.dp))
                    Surface(
                        color = MaterialTheme.colorScheme.surface,
                        shape = RoundedCornerShape(CardCorner),
                        border = androidx.compose.foundation.BorderStroke(
                            1.dp, MaterialTheme.colorScheme.outline,
                        ),
                    ) {
                        Text(
                            "Hours are computed offline from the curated dataset. Expense entry " +
                                "arrives with TB2 and is deliberately absent rather than stubbed.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(12.dp),
                        )
                    }
                    Spacer(Modifier.height(4.dp))
                }
            }

            byCluster.forEach { (cluster, group) ->
                item(key = "h-$cluster") {
                    Text(
                        cluster.uppercase(),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(MaterialTheme.colorScheme.background)
                            .padding(16.dp, 16.dp, 16.dp, 6.dp),
                    )
                }
                items(group, key = { it.id }) { place ->
                    PlaceRow(place, states.getValue(place.id)) { onOpen(place) }
                    HorizontalDivider(color = MaterialTheme.colorScheme.outline)
                }
            }
        }
    }
}

@Composable
private fun PlaceRow(place: Place, state: OpenState, onClick: () -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(16.dp, 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Column(Modifier.weight(1f)) {
            Text(
                place.name,
                style = MaterialTheme.typography.titleMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                stateLabel(state) + costSuffix(place),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        StatePill(state)
    }
}

@Composable
fun StatePill(state: OpenState) {
    val (label, color) = when (state) {
        is OpenState.Open -> "open" to MaterialTheme.colorScheme.secondary
        is OpenState.LikelyOpen -> "likely" to MaterialTheme.colorScheme.primary
        is OpenState.Closed -> "closed" to MaterialTheme.colorScheme.error
        OpenState.Unknown -> "unverified" to MaterialTheme.colorScheme.onSurfaceVariant
    }
    Text(
        label,
        style = MaterialTheme.typography.labelSmall,
        color = color,
        modifier = Modifier
            .border(1.dp, color, RoundedCornerShape(6.dp))
            .padding(horizontal = 7.dp, vertical = 2.dp),
    )
}

/** Human phrasing for a state, including *why* something is shut. */
fun stateLabel(state: OpenState): String = when (state) {
    is OpenState.Open ->
        if (state.minutesLeft in 1..60) "Closing in ${state.minutesLeft}m"
        else if (state.minutesLeft == Int.MAX_VALUE) "Always open — no gate"
        else "Open until ${state.closesAt}"
    is OpenState.LikelyOpen -> "Open since ${state.since} · closing time unverified"
    is OpenState.Closed -> when (state.reason) {
        ClosedReason.WEEKLY_CLOSURE -> "Closed all day today"
        ClosedReason.OUTSIDE_HOURS ->
            state.opensAt?.let { "Opens $it" } ?: "Closed for today"
    }
    OpenState.Unknown -> "Hours not verified"
}

private fun costSuffix(place: Place): String {
    val c = place.cost ?: return " · price unverified"
    return if (c.isZero) " · free" else " · ${c.format()}"
}

@Composable
fun PlaceDetailScreen(place: Place, onBack: () -> Unit) {
    BackHandler(onBack = onBack)
    val now = remember { Clock.System.now() }
    val state = remember(place.id) { place.hours.stateAt(now, MUMBAI) }
    val d = place.dto

    Scaffold { inner ->
        LazyColumn(
            modifier = Modifier.padding(inner),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            item {
                Text(
                    "‹ Places",
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.clickable(onClick = onBack),
                )
            }
            item {
                Column {
                    Text(d.name, style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold)
                    d.nameLocal?.let {
                        Text(it, style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Spacer(Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        StatePill(state)
                        ConfidencePill(d.confidence)
                    }
                }
            }

            // Rules above the photo, per the §7 wireframe: the rules are the product.
            item { SectionCard("BEFORE YOU GO") { d.insiderRules.forEach { Bullet(it) } } }

            item {
                SectionCard("HOURS") {
                    Text(stateLabel(state), style = MaterialTheme.typography.bodyMedium)
                    place.hours.note?.let {
                        Spacer(Modifier.height(6.dp))
                        Text(it, style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }

            item {
                SectionCard("THE BASICS") {
                    KeyVal("What it is", d.whatItIs)
                    KeyVal("Why locals rate it", d.whyLocalsRateIt)
                    KeyVal(
                        "Cost",
                        place.cost?.let { if (it.isZero) "Free" else it.format() }
                            ?: "Unverified — ships empty rather than guessed",
                    )
                    KeyVal(
                        "Getting there",
                        buildString {
                            append(d.howToGetThere.nearestStation ?: "No nearby station")
                            d.howToGetThere.line?.let { append(" ($it)") }
                            d.howToGetThere.walkMinutes?.let { append(" + $it min walk") }
                        },
                    )
                    KeyVal("In monsoon", d.monsoonSafe + (d.monsoonNote?.let { " — $it" } ?: ""))
                    KeyVal("Safety", d.safetyNotes)
                    KeyVal("Access", d.accessibility)
                }
            }

            item {
                SectionCard("SOURCES — ${d.sources.size}") {
                    d.confidenceNote?.let {
                        Text("Caveat: $it", style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.error)
                        Spacer(Modifier.height(8.dp))
                    }
                    d.sources.forEach { s ->
                        Text(
                            s.url,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.primary,
                        )
                        Text(
                            "supports ${s.supports.joinToString(", ")}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(Modifier.height(6.dp))
                    }
                    Text(
                        "Coordinates unresolved — no OSM provenance yet, so no map is drawn. " +
                            "Reviewed ${d.lastReviewed}.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

@Composable
private fun ConfidencePill(confidence: String) {
    val color = when (confidence) {
        "high" -> MaterialTheme.colorScheme.secondary
        "low" -> MaterialTheme.colorScheme.error
        else -> MaterialTheme.colorScheme.primary
    }
    Text(
        "$confidence confidence",
        style = MaterialTheme.typography.labelSmall,
        color = color,
        modifier = Modifier
            .border(1.dp, color, RoundedCornerShape(6.dp))
            .padding(horizontal = 7.dp, vertical = 2.dp),
    )
}

@Composable
private fun SectionCard(title: String, content: @Composable () -> Unit) {
    Surface(
        color = MaterialTheme.colorScheme.surface,
        shape = RoundedCornerShape(CardCorner),
        border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
    ) {
        Column(Modifier.padding(14.dp)) {
            Text(title, style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(8.dp))
            content()
        }
    }
}

@Composable
private fun Bullet(text: String) {
    Row(Modifier.padding(bottom = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("·", color = MaterialTheme.colorScheme.primary)
        Text(text, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun KeyVal(key: String, value: String) {
    if (value.isBlank()) return
    Column(Modifier.padding(bottom = 10.dp)) {
        Text(key, style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyMedium)
    }
}
