package com.mumbai.domain

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class CategoriesTest {

    /** The seed taxonomy, which already needs three levels — hence ADR-004 dropping the cap of 3. */
    private val seed = listOf(
        Category("food", null, "Food & Drink"),
        Category("food-chai", "food", "Chai & snacks"),
        Category("travel", null, "Travel"),
        Category("travel-local", "travel", "Local"),
        Category("travel-local-train", "travel-local", "Suburban train"),
        Category("travel-local-auto", "travel-local", "Auto rickshaw"),
        Category("travel-long", "travel", "Long distance"),
        Category("travel-long-train", "travel-long", "Intercity train"),
    )

    private val tree = CategoryTree(seed)

    private val spend = listOf(
        CategoryAmount("travel-long-train", Paise(76800)),   // the real inbound fare
        CategoryAmount("travel-long-train", Paise(74300)),   // the real outbound fare
        CategoryAmount("travel-local-auto", Paise(14000)),
        CategoryAmount("travel-local-train", Paise(1000)),
        CategoryAmount("food-chai", Paise(4000)),
    )

    @Test
    fun `the seed taxonomy is three deep, which the old cap would have broken`() {
        assertEquals(2, tree.depth("travel-local-train"))
        assertEquals("Travel ▸ Local ▸ Suburban train", tree.label("travel-local-train"))
        assertEquals(0, tree.depth("travel"))
    }

    @Test
    fun `roll-up reaches every ancestor`() {
        assertEquals(Paise(1000), tree.rollUp("travel-local-train", spend))
        assertEquals(Paise(15000), tree.rollUp("travel-local", spend))
        assertEquals(Paise(151100), tree.rollUp("travel-long", spend))
        assertEquals(Paise(166100), tree.rollUp("travel", spend))
        assertEquals(Paise(4000), tree.rollUp("food", spend))
    }

    @Test
    fun `a parent is never less than the sum of its children`() {
        for (c in seed) {
            val childSum = tree.children(c.id).map { tree.rollUp(it.id, spend) }.sum()
            assertTrue(
                tree.rollUp(c.id, spend) >= childSum,
                "${c.id} rolled up to less than its children — the bug rollUp exists to prevent",
            )
        }
    }

    @Test
    fun `roots roll up to the grand total`() {
        val byRoot = tree.rollUpByRoot(spend)
        assertEquals(Paise(170100), byRoot.map { it.second }.sum())
        assertEquals(spend.map { it.amount }.sum(), byRoot.map { it.second }.sum())
    }

    @Test
    fun `empty roots are omitted rather than shown as zero rows`() {
        val withEmpty = CategoryTree(seed + Category("stay", null, "Stay"))
        assertTrue(withEmpty.rollUpByRoot(spend).none { it.first.id == "stay" })
    }

    @Test
    fun `roll-up stays correct at depth six`() {
        // ADR-004 claims a recursive roll-up costs the same at depth 3 or depth 8. Prove it works.
        val deep = (0..6).map { i ->
            Category("d$i", if (i == 0) null else "d${i - 1}", "Level $i")
        }
        val t = CategoryTree(deep)
        val amounts = listOf(CategoryAmount("d6", Paise(500)))
        assertEquals(6, t.depth("d6"))
        assertEquals(Paise(500), t.rollUp("d0", amounts))
        assertEquals(Paise(500), t.rollUp("d3", amounts))
    }

    // ------------------------------------------------------------------ deletion

    @Test
    fun `deleting a node reparents its children and moves its expenses up`() {
        val plan = tree.planDelete("travel-local")
        assertIs<DeletePlan.Reparent>(plan)
        assertEquals("travel", plan.newParentId)
        assertEquals(
            setOf("travel-local-train", "travel-local-auto"),
            plan.reparentedChildren.map { it.id }.toSet(),
        )
        assertTrue(plan.reparentedChildren.all { it.parentId == "travel" })
    }

    @Test
    fun `no expense is orphaned or deleted with its category`() {
        val plan = tree.planDelete("travel-local-auto")
        assertIs<DeletePlan.Reparent>(plan)

        val after = spend.applyReassign(plan)
        assertEquals(spend.size, after.size, "no expense may be dropped")
        assertEquals(spend.map { it.amount }.sum(), after.map { it.amount }.sum(), "total must hold")
        assertTrue(after.none { it.categoryId == "travel-local-auto" }, "none may point at the dead id")
        assertEquals(Paise(15000), CategoryTree(seed - tree["travel-local-auto"]!!).rollUp("travel-local", after))
    }

    @Test
    fun `the whole tree stays valid after a real delete`() {
        val plan = tree.planDelete("travel-local")
        assertIs<DeletePlan.Reparent>(plan)

        val remaining = seed
            .filter { it.id != "travel-local" }
            .map { c -> plan.reparentedChildren.firstOrNull { it.id == c.id } ?: c }

        // Would throw on a dangling parent, which is the failure mode being guarded.
        val rebuilt = CategoryTree(remaining)
        val after = spend.applyReassign(plan)
        assertEquals(Paise(166100), rebuilt.rollUp("travel", after), "total under Travel is unchanged")
        assertEquals(1, rebuilt.depth("travel-local-train"), "moved up one level")
    }

    @Test
    fun `deleting a top-level node with children is blocked, not silently destructive`() {
        val plan = tree.planDelete("travel")
        assertIs<DeletePlan.Blocked>(plan)
        assertTrue(plan.why.contains("top-level"))
    }

    @Test
    fun `deleting a leaf root is allowed`() {
        val t = CategoryTree(seed + Category("stay", null, "Stay"))
        assertIs<DeletePlan.Reparent>(t.planDelete("stay"))
    }

    @Test
    fun `deleting something that is not there is reported, not thrown`() {
        assertIs<DeletePlan.NotFound>(tree.planDelete("nope"))
    }

    // ------------------------------------------------------------------ integrity

    @Test
    fun `a dangling parent is rejected at construction`() {
        assertNotNull(
            runCatching { CategoryTree(listOf(Category("a", "ghost", "A"))) }.exceptionOrNull(),
        )
    }

    @Test
    fun `a cycle is rejected rather than hanging`() {
        assertNotNull(
            runCatching {
                CategoryTree(listOf(Category("a", "b", "A"), Category("b", "a", "B")))
            }.exceptionOrNull(),
        )
    }
}
