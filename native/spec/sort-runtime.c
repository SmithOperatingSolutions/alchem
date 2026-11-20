/* The pinned runtime's two sorts, as Go 1.27.4 has them (sort/zsortfunc.go,
   slices/zsortanyfunc.go): stable_func (insertion sort over blocks of 20,
   then SymMerge) and pdqsort_func. Both ask "is d[i] less than d[j]" through
   a function value of the program and swap words in place, in the order Go
   does, so that a function that is no order gives the same result.
   A function value is called with its address in R10 and its arguments in
   RDI and RSI, and keeps only RBP, RSP and R12 to R15. */
typedef long word;
typedef struct { word *d; void *g; } S;
static __attribute__((noinline)) int less(S *s, long i, long j) {
  word r;
  register void *c __asm__("r10") = s->g;
  register word x __asm__("rdi") = s->d[i];
  register word y __asm__("rsi") = s->d[j];
  __asm__ volatile("call *(%%r10)" : "=a"(r), "+r"(c), "+r"(x), "+r"(y) : : "rbx", "rcx", "rdx", "r8", "r9", "r11", "memory", "cc");
  return (r & 255) != 0;
}
static inline void swap(S *s, long i, long j) { word t = s->d[i]; s->d[i] = s->d[j]; s->d[j] = t; }
static void insertion(S *s, long a, long b) {
  for (long i = a + 1; i < b; i++)
    for (long j = i; j > a && less(s, j, j - 1); j--) swap(s, j, j - 1);
}
#ifdef STABLE
static void swap_range(S *s, long a, long b, long n) { for (long i = 0; i < n; i++) swap(s, a + i, b + i); }
static void rotate(S *s, long a, long m, long b) {
  long i = m - a, j = b - m;
  while (i != j) {
    if (i > j) { swap_range(s, m - i, m, j); i -= j; }
    else { swap_range(s, m - i, m + j - i, i); j -= i; }
  }
  swap_range(s, m - i, m, i);
}
static void sym_merge(S *s, long a, long m, long b) {
  if (m - a == 1) {
    long i = m, j = b;
    while (i < j) { long h = (long)((unsigned long)(i + j) >> 1); if (less(s, h, a)) i = h + 1; else j = h; }
    for (long k = a; k < i - 1; k++) swap(s, k, k + 1);
    return;
  }
  if (b - m == 1) {
    long i = a, j = m;
    while (i < j) { long h = (long)((unsigned long)(i + j) >> 1); if (!less(s, m, h)) i = h + 1; else j = h; }
    for (long k = m; k > i; k--) swap(s, k, k - 1);
    return;
  }
  long mid = (long)((unsigned long)(a + b) >> 1), n = mid + m, start, r;
  if (m > mid) { start = n - b; r = mid; } else { start = a; r = m; }
  long p = n - 1;
  while (start < r) { long c = (long)((unsigned long)(start + r) >> 1); if (!less(s, p - c, c)) start = c + 1; else r = c; }
  long end = n - start;
  if (start < m && m < end) rotate(s, start, m, end);
  if (a < start && start < mid) sym_merge(s, a, start, mid);
  if (mid < end && end < b) sym_merge(s, mid, end, b);
}
void sort_entry(word *d, long n, void *g) {
  S c = {d, g}; S *s = &c;
  long block = 20, a = 0, b = block;
  while (b <= n) { insertion(s, a, b); a = b; b += block; }
  insertion(s, a, n);
  while (block < n) {
    a = 0; b = 2 * block;
    while (b <= n) { sym_merge(s, a, a + block, b); a = b; b += 2 * block; }
    long m = a + block;
    if (m < n) sym_merge(s, a, m, n);
    block *= 2;
  }
}
#else
static void sift_down(S *s, long lo, long hi, long first) {
  long root = lo;
  for (;;) {
    long child = 2 * root + 1;
    if (child >= hi) break;
    if (child + 1 < hi && less(s, first + child, first + child + 1)) child++;
    if (!less(s, first + root, first + child)) return;
    swap(s, first + root, first + child);
    root = child;
  }
}
static void heap_sort(S *s, long a, long b) {
  long first = a, lo = 0, hi = b - a;
  for (long i = (hi - 1) / 2; i >= 0; i--) sift_down(s, i, hi, first);
  for (long i = hi - 1; i >= 0; i--) { swap(s, first, first + i); sift_down(s, lo, i, first); }
}
static int bit_length(unsigned long x) { int n = 0; while (x) { n++; x >>= 1; } return n; }
static void break_patterns(S *s, long a, long b) {
  long length = b - a;
  if (length >= 8) {
    unsigned long random = (unsigned long)length;
    unsigned long modulus = 1UL << bit_length((unsigned long)length);
    for (long idx = a + (length / 4) * 2 - 1; idx <= a + (length / 4) * 2 + 1; idx++) {
      random ^= random << 13; random ^= random >> 7; random ^= random << 17;
      long other = (long)(random & (modulus - 1));
      if (other >= length) other -= length;
      swap(s, idx, a + other);
    }
  }
}
static long median(S *s, long a, long b, long c, long *swaps) {
  long t;
  if (less(s, b, a)) { (*swaps)++; t = a; a = b; b = t; }
  if (less(s, c, b)) { (*swaps)++; t = b; b = c; c = t; }
  if (less(s, b, a)) { (*swaps)++; t = a; a = b; b = t; }
  return b;
}
/* hint: 0 unknown, 1 increasing, 2 decreasing */
static long choose_pivot(S *s, long a, long b, long *hint) {
  long l = b - a, swaps = 0, i = a + l / 4 * 1, j = a + l / 4 * 2, k = a + l / 4 * 3;
  if (l >= 8) {
    if (l >= 50) { i = median(s, i - 1, i, i + 1, &swaps); j = median(s, j - 1, j, j + 1, &swaps); k = median(s, k - 1, k, k + 1, &swaps); }
    j = median(s, i, j, k, &swaps);
  }
  *hint = swaps == 0 ? 1 : swaps == 12 ? 2 : 0;
  return j;
}
static int partial_insertion(S *s, long a, long b) {
  long i = a + 1;
  for (long j = 0; j < 5; j++) {
    while (i < b && !less(s, i, i - 1)) i++;
    if (i == b) return 1;
    if (b - a < 50) return 0;
    swap(s, i, i - 1);
    if (i - a >= 2) for (long q = i - 1; q >= 1; q--) { if (!less(s, q, q - 1)) break; swap(s, q, q - 1); }
    if (b - i >= 2) for (long q = i + 1; q < b; q++) { if (!less(s, q, q - 1)) break; swap(s, q, q - 1); }
  }
  return 0;
}
static long partition_equal(S *s, long a, long b, long pivot) {
  swap(s, a, pivot);
  long i = a + 1, j = b - 1;
  for (;;) {
    while (i <= j && !less(s, a, i)) i++;
    while (i <= j && less(s, a, j)) j--;
    if (i > j) break;
    swap(s, i, j); i++; j--;
  }
  return i;
}
static long partition(S *s, long a, long b, long pivot, long *already) {
  swap(s, a, pivot);
  long i = a + 1, j = b - 1;
  while (i <= j && less(s, i, a)) i++;
  while (i <= j && !less(s, j, a)) j--;
  if (i > j) { swap(s, j, a); *already = 1; return j; }
  swap(s, i, j); i++; j--;
  for (;;) {
    while (i <= j && less(s, i, a)) i++;
    while (i <= j && !less(s, j, a)) j--;
    if (i > j) break;
    swap(s, i, j); i++; j--;
  }
  swap(s, j, a); *already = 0; return j;
}
static void pdqsort(S *s, long a, long b, long limit) {
  long balanced = 1, partitioned = 1;
  for (;;) {
    long length = b - a;
    if (length <= 12) { insertion(s, a, b); return; }
    if (limit == 0) { heap_sort(s, a, b); return; }
    if (!balanced) { break_patterns(s, a, b); limit--; }
    long hint;
    long pivot = choose_pivot(s, a, b, &hint);
    if (hint == 2) {
      for (long i = a, j = b - 1; i < j; i++, j--) swap(s, i, j);
      pivot = (b - 1) - (pivot - a); hint = 1;
    }
    if (balanced && partitioned && hint == 1) { if (partial_insertion(s, a, b)) return; }
    if (a > 0 && !less(s, a - 1, pivot)) { a = partition_equal(s, a, b, pivot); continue; }
    long already;
    long mid = partition(s, a, b, pivot, &already);
    partitioned = already;
    long left = mid - a, right = b - mid, threshold = length / 8;
    if (left < right) { balanced = left >= threshold; pdqsort(s, a, mid, limit); a = mid + 1; }
    else { balanced = right >= threshold; pdqsort(s, mid + 1, b, limit); b = mid; }
  }
}
void sort_entry(word *d, long n, void *g) {
  S c = {d, g};
  pdqsort(&c, 0, n, bit_length((unsigned long)n));
}
#endif
