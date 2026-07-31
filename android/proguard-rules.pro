# kotlinx.serialization keeps its generated serializers via @Serializable; R8 needs the hint.
-keepclassmembers class **$$serializer { *; }
-keepclasseswithmembers class * { @kotlinx.serialization.Serializable <fields>; }
-dontwarn kotlinx.serialization.**
