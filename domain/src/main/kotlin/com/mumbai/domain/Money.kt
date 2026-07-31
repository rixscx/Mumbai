package com.mumbai.domain

/**
 * An amount of money, in integer paise.
 *
 * The type exists so that money cannot silently become a `Double` somewhere downstream. Every
 * rounding bug in an expense tracker starts with one innocent division, and a value class costs
 * nothing at runtime — [Paise] is erased to a `Long` in the bytecode.
 *
 * There is deliberately no `div(Int)` returning [Paise] without a stated rounding rule: see
 * [splitEvenly], which is explicit about who absorbs the remainder.
 */
@JvmInline
value class Paise(val value: Long) : Comparable<Paise> {

    init {
        // A negative *amount* is meaningful (a refund), but a negative *total* usually means a
        // sign error upstream, so the guard is left to callers rather than forbidden here.
        require(value > Long.MIN_VALUE) { "paise out of range" }
    }

    operator fun plus(other: Paise) = Paise(value + other.value)
    operator fun minus(other: Paise) = Paise(value - other.value)
    operator fun times(n: Int) = Paise(value * n)
    operator fun unaryMinus() = Paise(-value)

    override fun compareTo(other: Paise): Int = value.compareTo(other.value)

    val isZero: Boolean get() = value == 0L
    val isNegative: Boolean get() = value < 0L

    /** Whole rupees, truncated toward zero. For display only — never for arithmetic. */
    val rupees: Long get() = value / 100

    /** The paise part, always 0..99, regardless of sign. */
    val fraction: Int get() = ((if (value < 0) -value else value) % 100).toInt()

    /**
     * Split across [ways], distributing the remainder one paisa at a time from the front.
     *
     * ₹100 three ways is 3334 + 3333 + 3333, not three lots of 3333 with a paisa lost. The
     * remainder has to land somewhere and pretending otherwise is how totals stop reconciling.
     */
    fun splitEvenly(ways: Int): List<Paise> {
        require(ways > 0) { "cannot split $ways ways" }
        val base = value / ways
        val remainder = (value % ways).toInt()
        val sign = if (remainder < 0) -1 else 1
        val extra = if (remainder < 0) -remainder else remainder
        return List(ways) { i -> Paise(base + if (i < extra) sign.toLong() else 0L) }
    }

    /** `₹1,240` / `₹1,240.50`. Indian digit grouping: last three, then pairs. */
    fun format(withSymbol: Boolean = true): String {
        val sb = StringBuilder()
        if (isNegative) sb.append('−')
        if (withSymbol) sb.append('₹')
        sb.append(groupIndian(if (rupees < 0) -rupees else rupees))
        if (fraction != 0) sb.append('.').append(fraction.toString().padStart(2, '0'))
        return sb.toString()
    }

    override fun toString(): String = format()

    companion object {
        val ZERO = Paise(0)

        fun ofRupees(rupees: Long): Paise = Paise(rupees * 100)

        /**
         * Parse what a person typed. Accepts `140`, `140.5`, `140.50`, `1,240`, `.5`.
         * Returns null rather than throwing: bad input at a keypad is normal, not exceptional.
         */
        fun parse(input: String): Paise? {
            val cleaned = input.trim().replace(",", "").replace(" ", "")
            if (cleaned.isEmpty()) return null
            val m = Regex("""^(-?)(\d*)(?:\.(\d{1,2}))?$""").matchEntire(cleaned) ?: return null
            val (sign, whole, frac) = m.destructured
            if (whole.isEmpty() && frac.isEmpty()) return null
            val rupees = if (whole.isEmpty()) 0L else whole.toLongOrNull() ?: return null
            val paise = if (frac.isEmpty()) 0L else frac.padEnd(2, '0').toLong()
            val total = rupees * 100 + paise
            return Paise(if (sign == "-") -total else total)
        }

        private fun groupIndian(n: Long): String {
            val s = n.toString()
            if (s.length <= 3) return s
            val head = s.dropLast(3)
            val tail = s.takeLast(3)
            val grouped = head.reversed().chunked(2).joinToString(",").reversed()
            return "$grouped,$tail"
        }
    }
}

/** Sum without leaving [Paise], so no call site is tempted into `Double`. */
fun Iterable<Paise>.sum(): Paise = fold(Paise.ZERO) { a, b -> a + b }
