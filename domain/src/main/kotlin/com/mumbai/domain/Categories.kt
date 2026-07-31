package com.mumbai.domain

/** A node in the expense taxonomy. Arbitrary depth, per ADR-004 — no cap of three. */
data class Category(val id: String, val parentId: String?, val name: String)

/** The minimum an expense has to be for category maths; the storage record carries more. */
data class CategoryAmount(val categoryId: String, val amount: Paise)

/**
 * The category tree, with the roll-up and deletion rules ADR-004 committed to.
 *
 * Built once per change rather than queried repeatedly: the whole tree for one traveller's trip is
 * a few dozen nodes, so an index built up front beats a recursive lookup per row.
 */
class CategoryTree(categories: List<Category>) {

    val all: List<Category> = categories
    private val byId: Map<String, Category> = categories.associateBy { it.id }
    private val childrenOf: Map<String?, List<Category>> = categories.groupBy { it.parentId }

    init {
        val ids = byId.keys
        val orphans = categories.filter { it.parentId != null && it.parentId !in ids }
        require(orphans.isEmpty()) {
            "categories reference missing parents: ${orphans.map { "${it.id}->${it.parentId}" }}"
        }
        categories.forEach { detectCycle(it) }
    }

    operator fun get(id: String): Category? = byId[id]

    fun roots(): List<Category> = childrenOf[null].orEmpty()

    fun children(id: String): List<Category> = childrenOf[id].orEmpty()

    /** The node itself plus every node beneath it. Breadth-first, so depth costs nothing extra. */
    fun descendants(id: String): List<String> {
        if (id !in byId) return emptyList()
        val out = mutableListOf(id)
        var i = 0
        while (i < out.size) {
            children(out[i]).forEach { out.add(it.id) }
            i++
        }
        return out
    }

    fun path(id: String): List<String> {
        val out = ArrayDeque<String>()
        var node = byId[id]
        var guard = 0
        while (node != null && guard++ < MAX_DEPTH) {
            out.addFirst(node.name)
            node = node.parentId?.let { byId[it] }
        }
        return out.toList()
    }

    fun label(id: String): String = path(id).joinToString(" ▸ ").ifEmpty { "Uncategorised" }

    fun depth(id: String): Int = (path(id).size - 1).coerceAtLeast(0)

    /**
     * Total for a category *including* everything nested under it.
     *
     * This is ADR-004's recursive roll-up. A parent that shows less than the sum of its children is
     * the bug this method exists to make impossible.
     */
    fun rollUp(id: String, amounts: Iterable<CategoryAmount>): Paise {
        val set = descendants(id).toHashSet()
        return amounts.filter { it.categoryId in set }.map { it.amount }.sum()
    }

    /** Roll-up for every root, in declaration order, skipping roots with nothing in them. */
    fun rollUpByRoot(amounts: Iterable<CategoryAmount>): List<Pair<Category, Paise>> =
        roots().map { it to rollUp(it.id, amounts) }.filter { !it.second.isZero }

    /**
     * What deleting [id] does. Returns the plan rather than performing it, so the caller can show
     * the consequences before committing — and so this is testable without a database.
     *
     * ADR-004's rule, exactly: children are reparented to the deleted node's parent, and expenses
     * are reassigned to that parent. **No expense is ever deleted with a category, and none is
     * left pointing at an id that no longer exists.**
     */
    fun planDelete(id: String): DeletePlan {
        val node = byId[id] ?: return DeletePlan.NotFound(id)
        val newParent = node.parentId
        val movedChildren = children(id).map { it.copy(parentId = newParent) }
        val affected = descendants(id)

        if (newParent == null) {
            val blockers = movedChildren.size
            if (blockers > 0) {
                return DeletePlan.Blocked(
                    id,
                    "\"${node.name}\" is top-level and has $blockers child categor" +
                        (if (blockers == 1) "y" else "ies") +
                        " — there is nowhere to reparent them. Move or delete those first.",
                )
            }
        }

        return DeletePlan.Reparent(
            deleted = node,
            newParentId = newParent,
            reparentedChildren = movedChildren,
            reassignFrom = id,
            reassignTo = newParent,
            descendantIds = affected,
        )
    }

    private fun detectCycle(start: Category) {
        var node: Category? = start
        var steps = 0
        while (node?.parentId != null) {
            node = byId[node.parentId]
            require(steps++ < MAX_DEPTH) { "category cycle involving '${start.id}'" }
        }
    }

    companion object {
        /** Not a cap on real depth — a loop guard, so malformed data fails loudly. */
        const val MAX_DEPTH = 64
    }
}

sealed interface DeletePlan {
    data class Reparent(
        val deleted: Category,
        val newParentId: String?,
        val reparentedChildren: List<Category>,
        val reassignFrom: String,
        val reassignTo: String?,
        val descendantIds: List<String>,
    ) : DeletePlan

    data class Blocked(val id: String, val why: String) : DeletePlan
    data class NotFound(val id: String) : DeletePlan
}

/** Apply a [DeletePlan.Reparent] to a list of expenses. Nothing is dropped. */
fun List<CategoryAmount>.applyReassign(plan: DeletePlan.Reparent): List<CategoryAmount> {
    val to = plan.reassignTo ?: return this
    return map { if (it.categoryId == plan.reassignFrom) it.copy(categoryId = to) else it }
}
