package com.mumbai.domain

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

class MoneyTest {

    @Test
    fun `parses what a person actually types`() {
        assertEquals(Paise(14000), Paise.parse("140"))
        assertEquals(Paise(14050), Paise.parse("140.50"))
        assertEquals(Paise(14050), Paise.parse("140.5"))
        assertEquals(Paise(124000), Paise.parse("1,240"))
        assertEquals(Paise(50), Paise.parse(".5"))
        assertEquals(Paise(5), Paise.parse("0.05"))
        assertEquals(Paise(0), Paise.parse("0"))
        assertEquals(Paise(-14000), Paise.parse("-140"))
        assertEquals(Paise(14000), Paise.parse("  140  "))
    }

    @Test
    fun `rejects rubbish rather than guessing`() {
        assertNull(Paise.parse(""))
        assertNull(Paise.parse("abc"))
        assertNull(Paise.parse("12.345"))   // more precision than paise exist
        assertNull(Paise.parse("1.2.3"))
        assertNull(Paise.parse("₹140"))     // the symbol is ours to add, not theirs to type
        assertNull(Paise.parse("."))
    }

    @Test
    fun `the two real ticket fares survive a round trip`() {
        // From the IRCTC slips in docs/TRIP.md. These are the only expenses this project ships.
        val inbound = Paise.parse("768.00")!!
        val outbound = Paise.parse("743.00")!!
        assertEquals(76800, inbound.value)
        assertEquals(74300, outbound.value)
        assertEquals("₹1,511", (inbound + outbound).format())
    }

    @Test
    fun `formats with Indian digit grouping`() {
        assertEquals("₹0", Paise.ZERO.format())
        assertEquals("₹5", Paise(500).format())
        assertEquals("₹140", Paise(14000).format())
        assertEquals("₹1,240", Paise(124000).format())
        assertEquals("₹30,000", Paise(3_000_000).format())
        assertEquals("₹1,84,420", Paise(18_442_000).format())   // lakh, not 184,420
        assertEquals("₹12,34,567", Paise(123_456_700).format())
        assertEquals("₹140.50", Paise(14050).format())
        assertEquals("−₹140", Paise(-14000).format())
    }

    @Test
    fun `splitting never loses a paisa`() {
        val parts = Paise(10000).splitEvenly(3)
        assertEquals(listOf(Paise(3334), Paise(3333), Paise(3333)), parts)
        assertEquals(Paise(10000), parts.sum())

        for (ways in 1..7) {
            for (amount in listOf(1L, 99L, 100L, 14000L, 76800L, 123457L)) {
                val split = Paise(amount).splitEvenly(ways)
                assertEquals(ways, split.size)
                assertEquals(Paise(amount), split.sum(), "$amount split $ways ways must reconcile")
            }
        }
    }

    @Test
    fun `negative splits also reconcile`() {
        val parts = Paise(-10000).splitEvenly(3)
        assertEquals(Paise(-10000), parts.sum())
    }

    @Test
    fun `fraction is unsigned and rupees truncate toward zero`() {
        assertEquals(40, Paise(14040).fraction)
        assertEquals(40, Paise(-14040).fraction)
        assertEquals(140, Paise(14040).rupees)
        assertEquals(-140, Paise(-14040).rupees)
    }

    @Test
    fun `sums and comparisons behave`() {
        assertEquals(Paise(300), listOf(Paise(100), Paise(200)).sum())
        assertEquals(Paise.ZERO, emptyList<Paise>().sum())
        assertTrue(Paise(200) > Paise(100))
        assertEquals(Paise(3_000_000), Paise.ofRupees(30_000))
    }
}
