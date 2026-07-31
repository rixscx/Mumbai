package com.mumbai

import android.app.Application
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.mumbai.data.Dataset
import com.mumbai.data.Place
import com.mumbai.ui.MumbaiTheme
import com.mumbai.ui.PlaceDetailScreen
import com.mumbai.ui.PlacesScreen

class MumbaiApp : Application()

/**
 * One activity, Compose throughout.
 *
 * This is TB1's slice of the Android app: the places checklist and a detail screen, both driven by
 * the curated dataset and by :domain's hours engine — the same logic that has 53 passing unit tests.
 * Expense entry, Room and SQLCipher are TB2 and are deliberately absent rather than stubbed, so
 * nothing here looks more finished than it is.
 */
class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)

        val places = Dataset.load(this)

        setContent {
            MumbaiTheme {
                var selected by mutableStateOf<Place?>(null)
                Router(places, selected) { selected = it }
            }
        }
    }
}

/**
 * Navigation is a single nullable selection rather than a nav library.
 *
 * Two screens do not justify a navigation graph, a dependency and a set of route strings; when the
 * third screen lands (expense entry, TB2) this becomes a real NavHost. Back is handled by the
 * detail screen itself so the system gesture works.
 */
@androidx.compose.runtime.Composable
private fun Router(places: List<Place>, selected: Place?, onSelect: (Place?) -> Unit) {
    if (selected == null) {
        PlacesScreen(places = places, onOpen = onSelect)
    } else {
        PlaceDetailScreen(place = selected, onBack = { onSelect(null) })
    }
}
