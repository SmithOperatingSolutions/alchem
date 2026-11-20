/* The Windows layer's calls written in C (spec/windows.md).

   spec/windows-x86_64.s takes each system call a program makes (ud2) and
   gives it first to layer_call here, with the CONTEXT Windows saved; what
   this returns is the call's result, or NOT_MINE for the calls the
   assembly makes. scripts/generate-windows-runtime.py compiles this file
   freestanding (no C library: the functions it needs are below) and links
   it with the assembly; Windows functions are called through the import
   address table, with the Windows calling convention (W). */

typedef unsigned long long u64;
typedef long long i64;
typedef unsigned int u32;
typedef int i32;
typedef unsigned short u16;
typedef short i16;
typedef unsigned char u8;

#define W __attribute__((ms_abi))
#define NOT_MINE 0x7FFFFFFFFFFFFFFFLL
#define FDS 1024

/* Linux errno values. */
enum {
  EPERM = 1, ENOENT = 2, EINTR = 4, EIO = 5, EBADF = 9, EAGAIN = 11,
  ENOMEM = 12, EACCES = 13, EFAULT = 14, EEXIST = 17, ENODEV = 19,
  EINVAL = 22, EMFILE = 24, ENOSPC = 28, EPIPE = 32, ENOSYS = 38,
  ENOTSOCK = 88, EDESTADDRREQ = 89, EMSGSIZE = 90, ENOPROTOOPT = 92,
  EPROTONOSUPPORT = 93, EOPNOTSUPP = 95, EAFNOSUPPORT = 97,
  EADDRINUSE = 98, EADDRNOTAVAIL = 99, ENETDOWN = 100, ENETUNREACH = 101,
  ECONNABORTED = 103, ECONNRESET = 104, ENOBUFS = 105, EISCONN = 106,
  ENOTCONN = 107, ETIMEDOUT = 110, ECONNREFUSED = 111, EHOSTUNREACH = 113,
  EALREADY = 114, EINPROGRESS = 115,
};

/* What the assembly keeps (spec/windows-x86_64.s). */
extern u64 handles[FDS];
extern u32 last_error;
extern W void commit_range(void *at, u64 length);
extern W u64 handle_of(u64 fd);
extern W i64 new_fd(u64 handle);
extern W i64 fail(void);
extern W i32 wide(const char *path, u16 *to);
extern u16 wpath1[32768], wpath2[32768];

/* Imports (the generator's IMPORTS). */
typedef u64 SOCKET;
extern W i32 (*imp_WSAStartup)(u16, void *);
extern W i32 (*imp_WSAGetLastError)(void);
extern W SOCKET (*imp_WSASocketW)(i32, i32, i32, void *, u32, u32);
extern W i32 (*imp_closesocket)(SOCKET);
extern W i32 (*imp_ioctlsocket)(SOCKET, i32, u32 *);
extern W i32 (*imp_bind)(SOCKET, const void *, i32);
extern W i32 (*imp_listen)(SOCKET, i32);
extern W SOCKET (*imp_accept)(SOCKET, void *, i32 *);
extern W i32 (*imp_connect)(SOCKET, const void *, i32);
extern W i32 (*imp_send)(SOCKET, const void *, i32, i32);
extern W i32 (*imp_sendto)(SOCKET, const void *, i32, i32, const void *, i32);
extern W i32 (*imp_recv)(SOCKET, void *, i32, i32);
extern W i32 (*imp_recvfrom)(SOCKET, void *, i32, i32, void *, i32 *);
extern W i32 (*imp_shutdown)(SOCKET, i32);
extern W i32 (*imp_getsockname)(SOCKET, void *, i32 *);
extern W i32 (*imp_getpeername)(SOCKET, void *, i32 *);
extern W i32 (*imp_setsockopt)(SOCKET, i32, i32, const void *, i32);
extern W i32 (*imp_getsockopt)(SOCKET, i32, i32, void *, i32 *);
extern W i32 (*imp_WSAPoll)(void *, u32, i32);
extern W i32 (*imp_ReadFile)(u64, void *, u32, u32 *, void *);
extern W i32 (*imp_WriteFile)(u64, const void *, u32, u32 *, void *);
extern W i32 (*imp_SetFilePointerEx)(u64, i64, i64 *, u32);
extern W i32 (*imp_SetEndOfFile)(u64);
extern W i32 (*imp_FlushFileBuffers)(u64);
extern W u32 (*imp_GetLastError)(void);
extern W void *(*imp_VirtualAlloc)(void *, u64, u32, u32);
extern W i32 (*imp_VirtualFree)(void *, u64, u32);
extern W i32 (*imp_GetFileInformationByHandleEx)(u64, i32, void *, u32);
extern W u32 (*imp_GetFinalPathNameByHandleW)(u64, u16 *, u32, u32);
extern W i32 (*imp_WideCharToMultiByte)(u32, u32, const u16 *, i32, char *, i32, void *, void *);
extern W i32 (*imp_CreateHardLinkW)(const u16 *, const u16 *, void *);
extern W u8 (*imp_CreateSymbolicLinkW)(const u16 *, const u16 *, u32);
extern W u32 (*imp_GetFileAttributesW)(const u16 *);
extern W i32 (*imp_SetFileAttributesW)(const u16 *, u32);
extern W u32 (*imp_GetTempPathW)(u32, u16 *);
extern W u32 (*imp_GetCurrentProcessId)(void);
extern W i32 (*imp_DuplicateHandle)(u64, u64, u64, u64 *, u32, i32, u32);
extern W u64 (*imp_GetCurrentProcess)(void);
extern W i32 (*imp_CloseHandle)(u64);
extern W u32 (*imp_FormatMessageW)(u32, const void *, u32, u32, u16 *, u32, void *);
extern W u32 (*imp_GetFullPathNameW)(const u16 *, u32, u16 *, u16 **);
extern W u64 (*imp_CreateFileW)(const u16 *, u32, u32, void *, u32, u32, u64);

/* gcc may call these even in freestanding code. */
void *memcpy(void *to, const void *from, u64 n) {
  void *t = to;
  __asm__ volatile("rep movsb" : "+D"(t), "+S"(from), "+c"(n) : : "memory");
  return to;
}
void *memset(void *to, int c, u64 n) {
  u8 *t = to;
  while (n--) *t++ = (u8)c;
  return to;
}

/* The arguments of the Linux call in the CONTEXT: RDI, RSI, RDX, R10, R8,
   R9. */
#define ARG(c, i) (*(i64 *)((c) + (u64[]){0xB0, 0xA8, 0x88, 0xC8, 0xB8, 0xC0}[i]))

/* The Windows error behind each errno the layer last gave (0: none, the
   errno was the layer's own). Sys.errno's text is Windows' for it, as Go's
   syscall.Errno.Error gives it (pseudo call 1000101). */
static u32 kept[4096];

/* --- Descriptors that are sockets ---------------------------------- */

/* 1 where the descriptor's handle is a socket. */
static u8 socket_fd[FDS];

static int is_socket(i64 fd) {
  return fd >= 0 && fd < FDS && socket_fd[fd] && handles[fd];
}

static i64 new_socket_fd(SOCKET s) {
  for (int fd = 3; fd < FDS; fd++)
    if (!handles[fd]) {
      handles[fd] = s;
      socket_fd[fd] = 1;
      return fd;
    }
  imp_closesocket(s);
  return -EMFILE;
}

/* The Linux errno that stands for a Winsock error. */
static i64 wsa_errno(i32 e) {
  switch (e) {
  case 10004: return EINTR;          /* WSAEINTR */
  case 10009: return EBADF;          /* WSAEBADF */
  case 10013: return EACCES;         /* WSAEACCES */
  case 10014: return EFAULT;         /* WSAEFAULT */
  case 10022: return EINVAL;         /* WSAEINVAL */
  case 10024: return EMFILE;         /* WSAEMFILE */
  case 10035: return EAGAIN;         /* WSAEWOULDBLOCK */
  case 10036: return EINPROGRESS;    /* WSAEINPROGRESS */
  case 10037: return EALREADY;       /* WSAEALREADY */
  case 10038: return ENOTSOCK;       /* WSAENOTSOCK */
  case 10039: return EDESTADDRREQ;   /* WSAEDESTADDRREQ */
  case 10040: return EMSGSIZE;       /* WSAEMSGSIZE */
  case 10042: return ENOPROTOOPT;    /* WSAENOPROTOOPT */
  case 10043: return EPROTONOSUPPORT;/* WSAEPROTONOSUPPORT */
  case 10045: return EOPNOTSUPP;     /* WSAEOPNOTSUPP */
  case 10047: return EAFNOSUPPORT;   /* WSAEAFNOSUPPORT */
  case 10048: return EADDRINUSE;     /* WSAEADDRINUSE */
  case 10049: return EADDRNOTAVAIL;  /* WSAEADDRNOTAVAIL */
  case 10050: return ENETDOWN;       /* WSAENETDOWN */
  case 10051: return ENETUNREACH;    /* WSAENETUNREACH */
  case 10052: return ECONNRESET;     /* WSAENETRESET */
  case 10053: return ECONNABORTED;   /* WSAECONNABORTED */
  case 10054: return ECONNRESET;     /* WSAECONNRESET */
  case 10055: return ENOBUFS;        /* WSAENOBUFS */
  case 10056: return EISCONN;        /* WSAEISCONN */
  case 10057: return ENOTCONN;       /* WSAENOTCONN */
  case 10058: return EPIPE;          /* WSAESHUTDOWN */
  case 10060: return ETIMEDOUT;      /* WSAETIMEDOUT */
  case 10061: return ECONNREFUSED;   /* WSAECONNREFUSED */
  case 10065: return EHOSTUNREACH;   /* WSAEHOSTUNREACH */
  case 10101: return ECONNABORTED;   /* WSAEDISCON */
  default: return EIO;
  }
}

/* -errno for the last Winsock error, which is kept as the Windows error. */
static i64 wsa_fail(void) {
  i32 e = imp_WSAGetLastError();
  last_error = (u32)e;
  return -wsa_errno(e);
}

static int started;
static int start(void) {
  if (!started) {
    u8 data[512];
    if (imp_WSAStartup(0x0202, data) != 0) return 0;
    started = 1;
  }
  return 1;
}

/* Addresses: Linux and Winsock lay out sockaddr_in and sockaddr_in6 alike;
   only AF_INET6 differs (10 and 23). */
#define LINUX_INET6 10
#define WINDOWS_INET6 23

static i32 to_windows(const u8 *from, i64 length, u8 *to) {
  if (length < 2 || length > 128) return -1;
  commit_range((void *)from, (u64)length);
  memcpy(to, from, (u64)length);
  if (*(u16 *)to == LINUX_INET6) *(u16 *)to = WINDOWS_INET6;
  return (i32)length;
}

/* The Winsock address in buffer (length n) to Linux at to, with its room
   at *room, which becomes its length, as Linux does: cut to the room. */
static void to_linux(u8 *buffer, i32 n, u8 *to, u32 *room) {
  if (!to || !room) return;
  commit_range(room, 4);
  if (n >= 2 && *(u16 *)buffer == WINDOWS_INET6) *(u16 *)buffer = LINUX_INET6;
  u32 r = *room;
  commit_range(to, r);
  memcpy(to, buffer, (u64)(r < (u32)n ? r : (u32)n));
  *room = (u32)n;
}

static i64 sys_socket(i64 family, i64 type, i64 protocol) {
  if (!start()) return -ENOSYS;
  i32 af = family == 2 ? 2 : family == LINUX_INET6 ? WINDOWS_INET6 : -1;
  if (af < 0) return -EAFNOSUPPORT;
  i32 kind = (i32)(type & 15);
  /* WSA_FLAG_OVERLAPPED | WSA_FLAG_NO_HANDLE_INHERIT, as Go makes them. */
  SOCKET s = imp_WSASocketW(af, kind, (i32)protocol, 0, 0, 0x01 | 0x80);
  if (s == (SOCKET)-1) return wsa_fail();
  if (type & 0x800) {                  /* SOCK_NONBLOCK */
    u32 on = 1;
    imp_ioctlsocket(s, (i32)0x8004667E, &on);
  }
  return new_socket_fd(s);
}

static i64 sys_connect(i64 fd, i64 address, i64 length) {
  u8 to[128];
  i32 n = to_windows((u8 *)address, length, to);
  if (n < 0) return -EINVAL;
  if (imp_connect(handles[fd], to, n) == 0) return 0;
  i64 r = wsa_fail();
  return r == -EAGAIN ? -EINPROGRESS : r;
}

static i64 sys_bind(i64 fd, i64 address, i64 length) {
  u8 to[128];
  i32 n = to_windows((u8 *)address, length, to);
  if (n < 0) return -EINVAL;
  return imp_bind(handles[fd], to, n) == 0 ? 0 : wsa_fail();
}

static i64 sys_accept(i64 fd, i64 address, i64 room, i64 flags) {
  u8 from[128];
  i32 n = sizeof from;
  SOCKET s = imp_accept(handles[fd], from, &n);
  if (s == (SOCKET)-1) return wsa_fail();
  u32 on = (flags & 0x800) ? 1 : 0;    /* SOCK_NONBLOCK */
  imp_ioctlsocket(s, (i32)0x8004667E, &on);
  to_linux(from, n, (u8 *)address, (u32 *)room);
  return new_socket_fd(s);
}

static i32 send_flags(i64 flags) {
  /* MSG_OOB and MSG_DONTROUTE are the same; MSG_DONTWAIT and MSG_NOSIGNAL
     have no Winsock flag (the sockets never block, nor raise a signal). */
  return (i32)(flags & 0x5);
}

static i64 sys_sendto(i64 fd, i64 data, i64 length, i64 flags, i64 address, i64 alength) {
  commit_range((void *)data, (u64)length);
  i32 n = length > 0x7FFFFFFF ? 0x7FFFFFFF : (i32)length;
  i32 r;
  if (address) {
    u8 to[128];
    i32 m = to_windows((u8 *)address, alength, to);
    if (m < 0) return -EINVAL;
    r = imp_sendto(handles[fd], (void *)data, n, send_flags(flags), to, m);
  } else {
    r = imp_send(handles[fd], (void *)data, n, send_flags(flags));
  }
  return r < 0 ? wsa_fail() : r;
}

static i64 sys_recvfrom(i64 fd, i64 data, i64 length, i64 flags, i64 address, i64 room) {
  commit_range((void *)data, (u64)length);
  i32 n = length > 0x7FFFFFFF ? 0x7FFFFFFF : (i32)length;
  /* MSG_OOB 1 and MSG_PEEK 2 are the same; MSG_DONTWAIT is not needed. */
  i32 f = (i32)(flags & 0x3);
  i32 r;
  if (address) {
    u8 from[128];
    i32 m = sizeof from;
    r = imp_recvfrom(handles[fd], (void *)data, n, f, from, &m);
    if (r >= 0) to_linux(from, m, (u8 *)address, (u32 *)room);
  } else {
    r = imp_recv(handles[fd], (void *)data, n, f);
  }
  if (r >= 0) return r;
  i64 e = wsa_fail();
  /* A datagram longer than the buffer: Linux gives what fits. */
  return e == -EMSGSIZE ? n : e;
}

static i64 sys_name(i64 fd, i64 address, i64 room, int peer) {
  u8 from[128];
  i32 n = sizeof from;
  i32 r = peer ? imp_getpeername(handles[fd], from, &n) : imp_getsockname(handles[fd], from, &n);
  if (r != 0) return wsa_fail();
  to_linux(from, n, (u8 *)address, (u32 *)room);
  return 0;
}

/* Socket options: the Linux level and name as Winsock's. 0 for an option
   Windows does without (SO_REUSEADDR: Go sets nothing on a Windows
   listener, which reuses addresses as is). */
static int option(i64 level, i64 name, i32 *wlevel, i32 *wname) {
  if (level == 1) {                    /* SOL_SOCKET */
    *wlevel = 0xFFFF;
    switch (name) {
    case 2: return 0;                  /* SO_REUSEADDR */
    case 4: *wname = 0x1007; return 1; /* SO_ERROR */
    case 6: *wname = 0x20; return 1;   /* SO_BROADCAST */
    case 7: *wname = 0x1001; return 1; /* SO_SNDBUF */
    case 8: *wname = 0x1002; return 1; /* SO_RCVBUF */
    case 9: *wname = 0x08; return 1;   /* SO_KEEPALIVE */
    case 13: *wname = 0x80; return 1;  /* SO_LINGER */
    }
  } else if (level == 6) {             /* IPPROTO_TCP */
    *wlevel = 6;
    switch (name) {
    case 1: *wname = 1; return 1;      /* TCP_NODELAY */
    case 4: *wname = 3; return 1;      /* TCP_KEEPIDLE: TCP_KEEPALIVE */
    case 5: *wname = 17; return 1;     /* TCP_KEEPINTVL */
    case 6: *wname = 16; return 1;     /* TCP_KEEPCNT */
    case 12: return 0;                 /* TCP_THIN_LINEAR_TIMEOUTS... none */
    }
  } else if (level == 41) {            /* IPPROTO_IPV6 */
    *wlevel = 41;
    if (name == 26) { *wname = 27; return 1; }   /* IPV6_V6ONLY */
  } else if (level == 0) {             /* IPPROTO_IP */
    *wlevel = 0;
    if (name == 2) { *wname = 4; return 1; }     /* IP_TTL */
  }
  return -1;
}

static i64 sys_setsockopt(i64 fd, i64 level, i64 name, i64 value, i64 length) {
  i32 wl, wn;
  int k = option(level, name, &wl, &wn);
  if (k < 0) return -ENOPROTOOPT;
  if (k == 0) return 0;
  commit_range((void *)value, (u64)length);
  if (wl == 0xFFFF && wn == 0x80) {    /* linger: two ints, two shorts */
    u16 l[2] = {(u16)((i32 *)value)[0], (u16)((i32 *)value)[1]};
    return imp_setsockopt(handles[fd], wl, wn, l, 4) == 0 ? 0 : wsa_fail();
  }
  return imp_setsockopt(handles[fd], wl, wn, (void *)value, (i32)length) == 0 ? 0 : wsa_fail();
}

static i64 sys_getsockopt(i64 fd, i64 level, i64 name, i64 value, i64 room) {
  i32 wl, wn;
  int k = option(level, name, &wl, &wn);
  if (k < 0) return -ENOPROTOOPT;
  commit_range((void *)room, 4);
  commit_range((void *)value, *(u32 *)room);
  if (k == 0) {
    *(i32 *)value = 0;
    *(u32 *)room = 4;
    return 0;
  }
  i32 v[4] = {0};
  i32 n = sizeof v;
  if (imp_getsockopt(handles[fd], wl, wn, v, &n) != 0) return wsa_fail();
  if (wl == 0xFFFF && wn == 0x1007 && v[0]) {
    /* The error of a connect that did not wait: its text is Windows'. */
    i64 n = wsa_errno(v[0]);
    kept[n] = (u32)v[0];
    v[0] = (i32)n;
  }
  u32 r = *(u32 *)room;
  memcpy((void *)value, v, r < 4 ? r : 4);
  *(u32 *)room = 4;
  return 0;
}

/* --- ppoll over sockets ------------------------------------------- */

struct linux_pollfd { i32 fd; i16 events, revents; };
struct windows_pollfd { SOCKET fd; i16 events, revents; };
static struct windows_pollfd polled[FDS];

/* ppoll(fds, count, timeout, mask) when a descriptor is a socket; NOT_MINE
   otherwise. A descriptor that is not a socket is taken as ready for what
   it waits for, as the assembly takes it. */
static i64 sys_ppoll(i64 fds, i64 count, i64 timeout) {
  if (count <= 0 || count > FDS) return NOT_MINE;
  struct linux_pollfd *p = (struct linux_pollfd *)fds;
  commit_range(p, (u64)count * 8);
  int sockets = 0, others = 0;
  for (i64 i = 0; i < count; i++) {
    if (is_socket(p[i].fd)) sockets++;
    else if (p[i].fd >= 0) others++;
  }
  if (!sockets) return NOT_MINE;
  i32 wait = -1;
  if (others) wait = 0;
  else if (timeout) {
    i64 *t = (i64 *)timeout;
    commit_range(t, 16);
    i64 ms = t[0] * 1000 + (t[1] + 999999) / 1000000;
    wait = ms > 0x7FFFFFFF ? 0x7FFFFFFF : (i32)ms;
  }
  u32 n = 0;
  for (i64 i = 0; i < count; i++) {
    if (!is_socket(p[i].fd)) continue;
    polled[n].fd = handles[p[i].fd];
    polled[n].events = (i16)(((p[i].events & 1) ? 0x100 : 0)    /* POLLRDNORM */
                             | ((p[i].events & 4) ? 0x10 : 0));  /* POLLWRNORM */
    polled[n].revents = 0;
    n++;
  }
  i32 r = imp_WSAPoll(polled, n, wait);
  if (r < 0) return wsa_fail();
  i64 ready = 0;
  n = 0;
  for (i64 i = 0; i < count; i++) {
    i16 got = 0;
    if (is_socket(p[i].fd)) {
      i16 w = polled[n++].revents;
      if (w & 0x300) got |= 1;         /* POLLRDNORM, POLLRDBAND: POLLIN */
      if (w & 0x10) got |= 4;          /* POLLWRNORM: POLLOUT */
      if (w & 0x1) got |= 8;           /* POLLERR */
      if (w & 0x2) got |= 0x10;        /* POLLHUP */
      if (w & 0x4) got |= 0x20;        /* POLLNVAL */
    } else if (p[i].fd >= 0) {
      got = p[i].events & 5;
    }
    p[i].revents = got;
    if (got) ready++;
  }
  return ready;
}


/* --- Files ---------------------------------------------------------- */

/* pread64 and pwrite64: at an offset, the file position kept (a
   synchronous handle's position moves with an offset read or write). */
static i64 sys_pio(i64 fd, i64 data, i64 length, i64 offset, int writing) {
  u64 h = handle_of((u64)fd);
  if (!h) return -EBADF;
  commit_range((void *)data, (u64)length);
  i64 kept;
  if (!imp_SetFilePointerEx(h, 0, &kept, 1)) return fail();
  u64 overlapped[4] = {0, 0, (u64)offset, 0};   /* Internal, InternalHigh, Offset+OffsetHigh, hEvent */
  u32 done = 0;
  u32 n = length > 0x7FFFF000 ? 0x7FFFF000 : (u32)length;
  i32 ok = writing ? imp_WriteFile(h, (void *)data, n, &done, overlapped)
                   : imp_ReadFile(h, (void *)data, n, &done, overlapped);
  i64 r = done;
  if (!ok) {
    u32 e = imp_GetLastError();
    if (writing || e != 38) r = fail();          /* ERROR_HANDLE_EOF: the end */
  }
  imp_SetFilePointerEx(h, kept, 0, 0);
  return r;
}

static i64 sys_ftruncate(i64 fd, i64 length) {
  u64 h = handle_of((u64)fd);
  if (!h) return -EBADF;
  i64 kept;
  if (!imp_SetFilePointerEx(h, 0, &kept, 1)) return fail();
  i64 r = 0;
  if (!imp_SetFilePointerEx(h, length, 0, 0) || !imp_SetEndOfFile(h)) r = fail();
  imp_SetFilePointerEx(h, kept, 0, 0);
  return r;
}

static i64 sys_fsync(i64 fd) {
  u64 h = handle_of((u64)fd);
  if (!h) return -EBADF;
  /* A directory, or a console or pipe, has nothing to flush. */
  if (imp_FlushFileBuffers(h)) return 0;
  u32 e = imp_GetLastError();
  return (e == 5 || e == 6 || e == 1) ? 0 : fail();
}

/* mmap of a file (not MAP_ANONYMOUS): the library maps only privately,
   to read, so the file's bytes are read into new memory. */
static i64 sys_mmap_file(i64 length, i64 fd, i64 offset) {
  if (length <= 0) return -EINVAL;
  void *m = imp_VirtualAlloc(0, (u64)length, 0x3000, 4);
  if (!m) return -ENOMEM;
  i64 got = 0;
  while (got < length) {
    i64 r = sys_pio(fd, (i64)m + got, length - got, offset + got, 0);
    if (r < 0) {
      imp_VirtualFree(m, 0, 0x8000);
      return r;
    }
    if (r == 0) break;
    got += r;
  }
  return (i64)m;
}

/* mremap(old, size, new size, MREMAP_MAYMOVE): a new mapping with the old
   contents; the old one is released. */
static i64 sys_mremap(i64 old, i64 size, i64 grown, i64 flags) {
  if (grown <= size) return old;
  if (!(flags & 1)) return -ENOMEM;
  void *m = imp_VirtualAlloc(0, (u64)grown, 0x3000, 4);
  if (!m) return -ENOMEM;
  commit_range((void *)old, (u64)size);
  memcpy(m, (void *)old, (u64)size);
  if (!imp_VirtualFree((void *)old, 0, 0x8000))           /* MEM_RELEASE */
    imp_VirtualFree((void *)old, (u64)size, 0x4000);       /* MEM_DECOMMIT */
  return (i64)m;
}

/* getdents64(fd, buffer, count): the directory's entries as Linux writes
   them, read from Windows FILE_FULL_DIR_INFO records. A Linux record is at
   most twice the room its Windows one takes, so Windows is given half the
   buffer and every record it gives fits. */
#define LISTING 32768
static u8 *listing;
static i64 sys_getdents(i64 fd, i64 buffer, i64 count) {
  u64 h = handle_of((u64)fd);
  if (!h) return -EBADF;
  commit_range((void *)buffer, (u64)count);
  if (!listing && !(listing = imp_VirtualAlloc(0, LISTING, 0x3000, 4))) return -ENOMEM;
  u32 room = (u32)(count / 2 > LISTING ? LISTING : count / 2);
  if (!imp_GetFileInformationByHandleEx(h, 14, listing, room)) {   /* FileFullDirectoryInfo */
    u32 e = imp_GetLastError();
    if (e == 18) return 0;                       /* ERROR_NO_MORE_FILES */
    if (e == 234) return -EINVAL;                /* ERROR_MORE_DATA: no room */
    return fail();
  }
  u8 *out = (u8 *)buffer;
  i64 used = 0;
  u32 at = 0;
  for (;;) {
    u8 *w = listing + at;
    u32 next = *(u32 *)w;
    u32 attributes = *(u32 *)(w + 56);
    u32 length = *(u32 *)(w + 60) / 2;
    u8 *r = out + used;
    i32 n = imp_WideCharToMultiByte(65001, 0, (u16 *)(w + 68), (i32)length, (char *)r + 19, (i32)(count - used - 20), 0, 0);
    if (n <= 0 && length) return -EINVAL;
    r[19 + n] = 0;
    u16 reclen = (u16)((19 + n + 1 + 7) & ~7);
    *(u64 *)r = (u64)(*(u32 *)(w + 4)) + 1;      /* d_ino */
    *(i64 *)(r + 8) = used + reclen;             /* d_off */
    *(u16 *)(r + 16) = reclen;
    r[18] = (attributes & 0x400) ? 10 : (attributes & 0x10) ? 4 : 8;   /* DT_LNK, DT_DIR, DT_REG */
    used += reclen;
    if (!next) break;
    at += next;
  }
  return used;
}

/* The UTF-8 path of directory descriptor fd joined with the relative path
   at path, in joined; 0 if it cannot be made. */
#define JOINED (3 * 32768 + 4)
static char *joined;
static int join_at(i64 fd, const char *path) {
  u64 h = handle_of((u64)fd);
  if (!h) return 0;
  if (!joined && !(joined = imp_VirtualAlloc(0, JOINED, 0x3000, 4))) return 0;
  u32 n = imp_GetFinalPathNameByHandleW(h, wpath2, 32768, 0);
  if (!n || n >= 32768) return 0;
  u16 *w = wpath2;
  /* \\?\C:\x is C:\x; \\?\UNC\server\x is \\server\x. */
  if (n >= 4 && w[0] == '\\' && w[1] == '\\' && w[2] == '?' && w[3] == '\\') {
    if (n >= 8 && w[4] == 'U' && w[5] == 'N' && w[6] == 'C' && w[7] == '\\') { w += 6; n -= 6; w[0] = '\\'; }
    else { w += 4; n -= 4; }
  }
  i32 m = imp_WideCharToMultiByte(65001, 0, w, (i32)n, joined, JOINED - 2, 0, 0);
  if (m <= 0) return 0;
  joined[m++] = '/';
  for (u64 i = 0; path[i]; i++) {
    if (m >= JOINED - 1) return 0;
    joined[m++] = path[i];
  }
  joined[m] = 0;
  return 1;
}

/* A call with a directory descriptor and a path in the arguments a and a+1
   that is not the working directory's: made by the assembly with the
   joined path, the program's registers restored after (layer_restore). */
static i64 restore_slot = -1;
static i64 restore_fd, restore_path;
static i64 at_call(unsigned char *c, int a) {
  i64 fd = ARG(c, a);
  const char *path = (const char *)ARG(c, a + 1);
  if (fd == -100 || !path) return NOT_MINE;
  commit_range((void *)path, 1);
  if (path[0] == '/' || path[0] == '\\' || (path[0] && path[1] == ':')) return NOT_MINE;
  if (!join_at(fd, path)) return -EBADF;
  restore_slot = a;
  restore_fd = fd;
  restore_path = (i64)path;
  ARG(c, a) = -100;
  ARG(c, a + 1) = (i64)joined;
  return NOT_MINE;
}

void layer_restore(unsigned char *c, i64 result) {
  /* The Windows error behind an errno the call gave, or none. */
  if (result < 0 && result > -4096) kept[-result] = last_error;
  if (restore_slot < 0) return;
  ARG(c, restore_slot) = restore_fd;
  ARG(c, restore_slot + 1) = restore_path;
  restore_slot = -1;
}

/* link(old, new) and symlink(target, link). */
static i64 sys_link(i64 old, i64 made, int symbolic) {
  if (!wide((const char *)old, wpath1) || !wide((const char *)made, wpath2)) return -ENOENT;
  if (!symbolic) return imp_CreateHardLinkW(wpath2, wpath1, 0) ? 0 : fail();
  /* Relative targets stay relative to the link; a directory's link is a
     directory link. SYMBOLIC_LINK_FLAG_ALLOW_UNPRIVILEGED_CREATE. */
  for (u16 *w = wpath1; *w; w++) if (*w == '/') *w = '\\';
  u32 attributes = imp_GetFileAttributesW(wpath1);
  u32 flags = 2 | ((attributes != 0xFFFFFFFF && (attributes & 0x10)) ? 1 : 0);
  return imp_CreateSymbolicLinkW(wpath2, wpath1, flags) ? 0 : fail();
}

/* fchmodat(dir, path, mode): Windows keeps only whether a file can be
   written (FILE_ATTRIBUTE_READONLY), as Go's os.Chmod does. */
static i64 sys_chmod(i64 path, i64 mode) {
  if (!wide((const char *)path, wpath1)) return -ENOENT;
  u32 a = imp_GetFileAttributesW(wpath1);
  if (a == 0xFFFFFFFF) return fail();
  a = (mode & 0200) ? (a & ~1u) : (a | 1u);
  if (!a) a = 0x80;                             /* FILE_ATTRIBUTE_NORMAL */
  return imp_SetFileAttributesW(wpath1, a) ? 0 : fail();
}

/* memfd_create(name, flags): a temporary file, deleted when closed. */
static u32 memfds;
static i64 sys_memfd(void) {
  u32 n = imp_GetTempPathW(32000, wpath1);
  if (!n || n > 32000) return -ENOENT;
  const char *tag = "alchem-memfd-";
  for (u32 i = 0; tag[i]; i++) wpath1[n++] = (u16)tag[i];
  u32 id = imp_GetCurrentProcessId(), k = ++memfds;
  for (int i = 0; i < 8; i++) wpath1[n++] = (u16)("0123456789abcdef"[(id >> (28 - 4 * i)) & 15]);
  wpath1[n++] = '-';
  for (int i = 0; i < 8; i++) wpath1[n++] = (u16)("0123456789abcdef"[(k >> (28 - 4 * i)) & 15]);
  wpath1[n] = 0;
  /* GENERIC_READ|WRITE, sharing all, CREATE_ALWAYS, TEMPORARY, DELETE_ON_CLOSE. */
  u64 h = imp_CreateFileW(wpath1, 0xC0000000, 7, 0, 2, 0x100 | 0x04000000, 0);
  if (h == (u64)-1) return fail();
  return new_fd(h);
}

/* --- Duplicates ----------------------------------------------------- */

/* The descriptor's handle duplicated, in *out; -errno or 0. */
static i64 duplicate(i64 fd, u64 *out) {
  u64 h = handle_of((u64)fd);
  if (!h) return -EBADF;
  u64 me = imp_GetCurrentProcess();
  /* DUPLICATE_SAME_ACCESS, not inherited. */
  return imp_DuplicateHandle(me, h, me, out, 0, 0, 2) ? 0 : fail();
}

static void release(i64 fd) {
  if (!handles[fd]) return;
  if (socket_fd[fd]) imp_closesocket(handles[fd]);
  else imp_CloseHandle(handles[fd]);
  handles[fd] = 0;
  socket_fd[fd] = 0;
}

/* dup2 and dup3: the duplicate at descriptor to, whatever was there closed. */
static i64 sys_dup2(i64 fd, i64 to) {
  if (to < 0 || to >= FDS) return -EBADF;
  if (fd == to) return handle_of((u64)fd) ? to : -EBADF;
  u64 h;
  i64 r = duplicate(fd, &h);
  if (r < 0) return r;
  u8 kind = (fd >= 0 && fd < FDS) ? socket_fd[fd] : 0;
  release(to);
  handles[to] = h;
  socket_fd[to] = kind;
  return to;
}

/* dup and fcntl's F_DUPFD: the duplicate at the lowest free descriptor from
   least. */
static i64 sys_dup(i64 fd, i64 least) {
  u64 h;
  i64 r = duplicate(fd, &h);
  if (r < 0) return r;
  if (least < 3) least = 3;
  for (i64 to = least; to < FDS; to++)
    if (!handles[to]) {
      handles[to] = h;
      socket_fd[to] = (fd >= 0 && fd < FDS) ? socket_fd[fd] : 0;
      return to;
    }
  imp_CloseHandle(h);
  return -EMFILE;
}

static i64 sys_fcntl(i64 fd, i64 command, i64 value) {
  switch (command) {
  case 0: case 1030: return sys_dup(fd, value);   /* F_DUPFD, F_DUPFD_CLOEXEC */
  case 1: case 2: return handle_of((u64)fd) ? 0 : -EBADF;   /* F_GETFD, F_SETFD */
  case 3: return handle_of((u64)fd) ? 02 : -EBADF;          /* F_GETFL: O_RDWR */
  case 4: return handle_of((u64)fd) ? 0 : -EBADF;           /* F_SETFL */
  }
  return -EINVAL;
}

/* --- The library's view of Windows ---------------------------------- */


/* UTF-16 at w (n units, or up to its zero when n < 0) as UTF-8 at out, with
   room bytes and a zero after; the length, or -1. */
static i32 utf8(const u16 *w, i32 n, char *out, i32 room) {
  i32 m = imp_WideCharToMultiByte(65001, 0, w, n, out, room - 1, 0, 0);
  if (m <= 0 && n != 0) return -1;
  if (n < 0 && m > 0) m--;                     /* the zero it counted */
  out[m] = 0;
  return m;
}

static char text[2048];

/* The text of errno n: FormatMessage of the Windows error kept for it, in
   US English if Windows has it, else in the user's language, without the
   line end; "winapi error #N" when Windows has none (as Go). */
static i64 error_text(i64 n) {
  if (n <= 0 || n >= 4096) return -ENOENT;
  /* An errno with no Windows error behind it (the library's or the
     layer's own) has Go's invented text, but ENOENT and ENOTDIR, which Go's
     syscall names for ERROR_FILE_NOT_FOUND and ERROR_PATH_NOT_FOUND. */
  u32 e = kept[n] ? kept[n] : n == ENOENT ? 2 : n == 20 ? 3 : 0;
  if (!e) return -ENOENT;
  /* FROM_SYSTEM | ARGUMENT_ARRAY | IGNORE_INSERTS */
  u32 flags = 0x1000 | 0x2000 | 0x200;
  u32 m = imp_FormatMessageW(flags, 0, e, 0x0409, wpath2, 300, 0);
  if (!m) m = imp_FormatMessageW(flags, 0, e, 0, wpath2, 300, 0);
  if (!m) {
    const char *head = "winapi error #";
    i32 k = 0;
    for (; head[k]; k++) text[k] = head[k];
    char digits[12];
    i32 d = 0;
    do { digits[d++] = (char)('0' + e % 10); e /= 10; } while (e);
    while (d) text[k++] = digits[--d];
    text[k] = 0;
    return (i64)text;
  }
  while (m && (wpath2[m - 1] == '\n' || wpath2[m - 1] == '\r')) m--;
  return utf8(wpath2, (i32)m, text, sizeof text) < 0 ? -EINVAL : (i64)text;
}

/* syscall.FullPath (GetFullPathNameW) of the UTF-8 path at p, in UTF-8. */
static i64 full_path(i64 p) {
  if (!wide((const char *)p, wpath1)) return -ENOENT;
  u32 n = imp_GetFullPathNameW(wpath1, 32768, wpath2, 0);
  if (!n || n >= 32768) return fail();
  if (!joined && !(joined = imp_VirtualAlloc(0, JOINED, 0x3000, 4))) return -ENOMEM;
  return utf8(wpath2, (i32)n, joined, JOINED) < 0 ? -EINVAL : (i64)joined;
}

/* os.TempDir: GetTempPathW, its last \ taken off unless it is C:\. */
static i64 temp_dir(void) {
  u32 n = imp_GetTempPathW(32768, wpath2);
  if (!n || n >= 32768) return -ENOENT;
  if (!(n == 3 && wpath2[1] == ':' && wpath2[2] == '\\') && wpath2[n - 1] == '\\') n--;
  return utf8(wpath2, (i32)n, text, sizeof text) < 0 ? -EINVAL : (i64)text;
}

/* --- Calls on a descriptor that is a socket ------------------------- */

static i64 socket_call(i64 nr, unsigned char *c) {
  i64 fd = ARG(c, 0);
  switch (nr) {
  case 0:  return sys_recvfrom(fd, ARG(c, 1), ARG(c, 2), 0, 0, 0);    /* read */
  case 1:  return sys_sendto(fd, ARG(c, 1), ARG(c, 2), 0, 0, 0);      /* write */
  case 3:                                                             /* close */
    imp_closesocket(handles[fd]);
    handles[fd] = 0;
    socket_fd[fd] = 0;
    return 0;
  case 5: {                                                           /* fstat */
    u8 *st = (u8 *)ARG(c, 1);
    commit_range(st, 144);
    memset(st, 0, 144);
    *(u32 *)(st + 24) = 0140777;       /* S_IFSOCK */
    *(u64 *)(st + 16) = 1;
    *(u64 *)(st + 56) = 4096;
    return 0;
  }
  case 16:                                                            /* ioctl */
    /* SIOCGIFINDEX, SIOCGIFNAME: no interface is known by Linux name. */
    return -ENODEV;
  case 42: return sys_connect(fd, ARG(c, 1), ARG(c, 2));
  case 43: return sys_accept(fd, ARG(c, 1), ARG(c, 2), 0);
  case 288: return sys_accept(fd, ARG(c, 1), ARG(c, 2), ARG(c, 3));
  case 44: return sys_sendto(fd, ARG(c, 1), ARG(c, 2), ARG(c, 3), ARG(c, 4), ARG(c, 5));
  case 45: return sys_recvfrom(fd, ARG(c, 1), ARG(c, 2), ARG(c, 3), ARG(c, 4), ARG(c, 5));
  case 48: return imp_shutdown(handles[fd], (i32)ARG(c, 1)) == 0 ? 0 : wsa_fail();
  case 49: return sys_bind(fd, ARG(c, 1), ARG(c, 2));
  case 50: return imp_listen(handles[fd], (i32)ARG(c, 1)) == 0 ? 0 : wsa_fail();
  case 51: return sys_name(fd, ARG(c, 1), ARG(c, 2), 0);
  case 52: return sys_name(fd, ARG(c, 1), ARG(c, 2), 1);
  case 54: return sys_setsockopt(fd, ARG(c, 1), ARG(c, 2), ARG(c, 3), ARG(c, 4));
  case 55: return sys_getsockopt(fd, ARG(c, 1), ARG(c, 2), ARG(c, 3), ARG(c, 4));
  case 72:                                                            /* fcntl */
    if (ARG(c, 1) == 0 || ARG(c, 1) == 1030) return sys_dup(fd, ARG(c, 2));
    if (ARG(c, 1) == 3) return 02 | 04000;          /* F_GETFL: O_RDWR | O_NONBLOCK */
    if (ARG(c, 1) == 4) {                           /* F_SETFL */
      u32 on = (ARG(c, 2) & 04000) ? 1 : 0;
      return imp_ioctlsocket(handles[fd], (i32)0x8004667E, &on) == 0 ? 0 : wsa_fail();
    }
    return 0;                                       /* F_GETFD, F_SETFD */
  }
  return NOT_MINE;
}

/* The system call in the CONTEXT at c (its number in RAX): its result, or
   NOT_MINE for the assembly to make. */
i64 layer_call(unsigned char *c) {
  i64 nr = *(i64 *)(c + 0x78);
  last_error = 0;
  switch (nr) {
  case 1000101: return error_text(ARG(c, 0));
  case 1000102: return full_path(ARG(c, 0));
  case 1000103: return temp_dir();
  case 41: return sys_socket(ARG(c, 0), ARG(c, 1), ARG(c, 2));
  case 271: return sys_ppoll(ARG(c, 0), ARG(c, 1), ARG(c, 2));
  case 0: case 1: case 3: case 5: case 16:
    return is_socket(ARG(c, 0)) ? socket_call(nr, c) : NOT_MINE;
  case 72: return is_socket(ARG(c, 0)) ? socket_call(nr, c) : sys_fcntl(ARG(c, 0), ARG(c, 1), ARG(c, 2));
  case 32: return sys_dup(ARG(c, 0), 3);
  case 33: case 292: return sys_dup2(ARG(c, 0), ARG(c, 1));
  case 17: return sys_pio(ARG(c, 0), ARG(c, 1), ARG(c, 2), ARG(c, 3), 0);
  case 18: return sys_pio(ARG(c, 0), ARG(c, 1), ARG(c, 2), ARG(c, 3), 1);
  case 9:                                                      /* mmap */
    if (ARG(c, 3) & 0x20 || ARG(c, 4) < 0) return NOT_MINE;
    return sys_mmap_file(ARG(c, 1), ARG(c, 4), ARG(c, 5));
  case 25: return sys_mremap(ARG(c, 0), ARG(c, 1), ARG(c, 2), ARG(c, 3));
  case 74: case 75: return sys_fsync(ARG(c, 0));               /* fsync, fdatasync */
  case 77: return sys_ftruncate(ARG(c, 0), ARG(c, 1));
  case 86: return sys_link(ARG(c, 0), ARG(c, 1), 0);
  case 88: return sys_link(ARG(c, 0), ARG(c, 1), 1);
  case 90: return sys_chmod(ARG(c, 0), ARG(c, 1));             /* chmod */
  case 217: return sys_getdents(ARG(c, 0), ARG(c, 1), ARG(c, 2));
  case 268: {                                                  /* fchmodat */
    i64 r = at_call(c, 0);
    if (r != NOT_MINE) return r;
    i64 path = ARG(c, 1), mode = ARG(c, 2);
    layer_restore(c, 0);
    return sys_chmod(path, mode);
  }
  case 319: return sys_memfd();
  case 257: case 258: case 262: case 263: return at_call(c, 0);   /* openat, mkdirat, newfstatat, unlinkat */
  case 264: case 316: {                                        /* renameat, renameat2 */
    if (ARG(c, 2) != -100 && ARG(c, 0) == -100) {
      /* Only the second is relative to a directory: not made. */
      if (ARG(c, 3) && ((const char *)ARG(c, 3))[0] != '/') return -ENOSYS;
    }
    return at_call(c, 0);
  }
  case 42: case 43: case 44: case 45: case 48: case 49: case 50: case 51:
  case 52: case 54: case 55: case 288:
    return is_socket(ARG(c, 0)) ? socket_call(nr, c) : -ENOTSOCK;
  }
  return NOT_MINE;
}
