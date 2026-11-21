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
  EINVAL = 22, EMFILE = 24, ENAMETOOLONG = 36, ENOSPC = 28, EPIPE = 32, ENOSYS = 38,
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
extern W void fill_stat(void *stat, const void *data, u64 size);
extern W void wait_for(const i64 *timespec);
extern u16 wpath1[32768], wpath2[32768];
extern u64 regions[][2];
extern u32 region_count;
#define REGIONS 1024
void region_add(u64 at, u64 size);
/* Set while a copy of the program runs (fork, below); the assembly's
   commit_range looks at it. */
int copy_running;
#define copying copy_running

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
extern W i32 (*imp_WSAIoctl)(SOCKET, u32, void *, u32, void *, u32, u32 *, void *, void *);
extern W i32 (*imp_select)(i32, void *, void *, void *, const void *);
extern W i32 (*imp_GetAddrInfoW)(const u16 *, const u16 *, const void *, void **);
extern W void (*imp_FreeAddrInfoW)(void *);
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
extern W i32 (*imp_GetFileAttributesExW)(const u16 *, u32, void *);
extern W i32 (*imp_SetFileAttributesW)(const u16 *, u32);
extern W u32 (*imp_GetTempPathW)(u32, u16 *);
extern W u32 (*imp_GetCurrentProcessId)(void);
extern W i32 (*imp_DuplicateHandle)(u64, u64, u64, u64 *, u32, i32, u32);
extern W u64 (*imp_GetCurrentProcess)(void);
extern W i32 (*imp_CloseHandle)(u64);
extern W u32 (*imp_FormatMessageW)(u32, const void *, u32, u32, u16 *, u32, void *);
extern W u32 (*imp_GetFullPathNameW)(const u16 *, u32, u16 *, u16 **);
extern W u32 (*imp_GetFileType)(u64);
extern W i32 (*imp_PeekNamedPipe)(u64, void *, u32, u32 *, u32 *, u32 *);
extern W u64 (*imp_CreateThread)(void *, u64, void *, void *, u32, u32 *);
extern W i32 (*imp_DeleteFileW)(const u16 *);
extern W i32 (*imp_RemoveDirectoryW)(const u16 *);
extern W void (*imp_SetLastError)(u32);
extern W i32 (*imp_DeviceIoControl)(u64, u32, void *, u32, void *, u32, u32 *, void *);
extern W u64 (*imp_FindFirstFileW)(const u16 *, void *);
extern W i32 (*imp_FindClose)(u64);
extern W i32 (*imp_GetFileInformationByHandle)(u64, void *);
extern W i32 (*imp_SetFileTime)(u64, const u64 *, const u64 *, const u64 *);
extern W void (*imp_GetSystemTimeAsFileTime)(u64 *);
extern W u64 (*imp_GetTickCount64)(void);
extern W i32 (*imp_MultiByteToWideChar)(u32, u32, const char *, i32, u16 *, i32);
extern W u32 (*imp_GetEnvironmentVariableW)(const u16 *, u16 *, u32);
extern W i32 (*imp_CreatePipe)(u64 *, u64 *, void *, u32);
extern W i32 (*imp_SetHandleInformation)(u64, u32, u32);
extern W i32 (*imp_CreateProcessW)(const u16 *, u16 *, void *, void *, i32, u32, void *, const u16 *, void *, void *);
extern W u32 (*imp_WaitForSingleObject)(u64, u32);
extern W i32 (*imp_GetExitCodeProcess)(u64, u32 *);
extern W i32 (*imp_TerminateProcess)(u64, u32);
extern W void (*imp_ExitProcess)(u32);
extern W i32 (*imp_CreateTimerQueueTimer)(u64 *, u64, W void (*)(void *, u8), void *, u32, u32, u32);
extern W i32 (*imp_DeleteTimerQueueTimer)(u64, u64, u64);
extern W void (*imp_RtlRestoreContext)(void *, void *);
extern void copy_resume(void);
extern W u64 (*imp_VirtualQuery)(const void *, void *, u64);
extern W i32 (*imp_VirtualProtect)(void *, u64, u32, u32 *);
extern W u32 (*imp_GetTimeZoneInformation)(void *);
extern W void (*imp_GetSystemTime)(u16 *);
extern W i32 (*imp_RegOpenKeyExW)(u64, const u16 *, u32, u32, u64 *);
extern W i32 (*imp_RegEnumKeyExW)(u64, u32, u16 *, u32 *, void *, void *, void *, void *);
extern W i32 (*imp_RegQueryValueExW)(u64, const u16 *, void *, u32 *, void *, u32 *);
extern W i32 (*imp_RegLoadMUIStringW)(u64, const u16 *, u16 *, u32, u32 *, u32, const u16 *);
extern W i32 (*imp_RegCloseKey)(u64);
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
  /* To the machine itself, Go's net asks for no retransmission of SYN
     (SIO_TCP_INITIAL_RTO), so that a port nothing listens on is refused at
     once, not after 2 s; an ioctl that fails changes nothing. */
  u16 family = *(u16 *)to;
  /* Go's net dials the zero address (0.0.0.0, ::, an empty host) on
     Windows as the machine itself (internetSocket, toLocal), where Windows
     refuses it as an address not valid in its context. */
  if (family == 2 && *(u32 *)(to + 4) == 0) *(u32 *)(to + 4) = 0x0100007F;
  if (family == WINDOWS_INET6 && *(u64 *)(to + 8) == 0 && *(u64 *)(to + 16) == 0) to[23] = 1;
  static const u8 loop6[16] = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1};
  int loopback = (family == 2 && to[4] == 127);
  if (family == WINDOWS_INET6) {
    loopback = 1;
    for (int i = 0; i < 16; i++) if (to[8 + i] != loop6[i]) loopback = 0;
  }
  if (loopback) {
    u8 params[4] = {0xFF, 0xFF, 0xFE, 0};     /* Rtt unspecified; TCP_INITIAL_RTO_NO_SYN_RETRANSMISSIONS */
    u32 out = 0;
    imp_WSAIoctl(handles[fd], 0x98000011, params, 4, 0, 0, &out, 0, 0);
  }
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

/* --- Names ------------------------------------------------------------

   Pseudo call 1000107 (TCP._resolve): the addresses of the host name at
   name as Go's net has them on Windows, from GetAddrInfoW (which reads the
   system's hosts file and knows localhost), into out (room bytes): each a
   length byte and the address as Linux lays it out (AF_INET6 10), port 0.
   Their count, or -ENOENT. */
static i64 sys_resolve(i64 name, i64 out, i64 room) {
  if (!start()) return -ENOSYS;
  if (!wide((const char *)name, wpath1)) return -ENOENT;
  i32 hints[12] = {0};
  hints[2] = 1;                                  /* SOCK_STREAM: each address once */
  u8 *list = 0;
  if (imp_GetAddrInfoW(wpath1, 0, hints, (void **)&list) != 0) return -ENOENT;
  u8 *o = (u8 *)out;
  commit_range(o, (u64)room);
  i64 used = 0, count = 0;
  for (u8 *a = list; a; a = *(u8 **)(a + 40)) {
    i32 family = *(i32 *)(a + 4);
    u8 *sa = *(u8 **)(a + 32);
    u64 n = family == 2 ? 16 : family == WINDOWS_INET6 ? 28 : 0;
    if (!n || !sa || used + 1 + (i64)n > room) continue;
    o[used] = (u8)n;
    memcpy(o + used + 1, sa, n);
    *(u16 *)(o + used + 1) = family == 2 ? 2 : LINUX_INET6;
    *(u16 *)(o + used + 3) = 0;
    used += 1 + (i64)n;
    count++;
  }
  imp_FreeAddrInfoW(list);
  return count ? count : -ENOENT;
}

/* --- ppoll ------------------------------------------------------------- */

struct linux_pollfd { i32 fd; i16 events, revents; };
struct windows_pollfd { SOCKET fd; i16 events, revents; };
static struct windows_pollfd polled[FDS];

/* What a descriptor that is not a socket is ready for: a pipe is ready to
   read when it holds bytes or its writer has gone (PeekNamedPipe); any
   other, and a pipe to write to, is ready for what it waits for. */
static i16 other_ready(i32 fd, i16 events) {
  u64 h = handle_of((u64)fd);
  if (!h) return 0x20;                         /* POLLNVAL */
  if (!(events & 1) || imp_GetFileType(h) != 3) return events & 5;   /* FILE_TYPE_PIPE */
  u32 avail = 0;
  if (imp_PeekNamedPipe(h, 0, 0, 0, &avail, 0)) return avail ? (i16)((events & 5)) : (i16)(events & 4);
  return (imp_GetLastError() == 109) ? (i16)(1 | 0x10) : (i16)8;     /* broken: the end; else POLLERR */
}

/* ppoll(fds, count, timeout, mask). With no descriptor it is the
   assembly's sleep (NOT_MINE). Sockets wait in WSAPoll; while a pipe is
   waited for, the descriptors are looked at again each millisecond, on the
   assembly's high-resolution timer, until the timeout. */
static i64 sys_ppoll(i64 fds, i64 count, i64 timeout) {
  if (count <= 0 || count > FDS) return NOT_MINE;
  struct linux_pollfd *p = (struct linux_pollfd *)fds;
  commit_range(p, (u64)count * 8);
  i64 limit = -1;                              /* ms; -1 for ever */
  if (timeout) {
    i64 *t = (i64 *)timeout;
    commit_range(t, 16);
    limit = t[0] * 1000 + (t[1] + 999999) / 1000000;
  }
  u64 start = imp_GetTickCount64();
  for (;;) {
    u32 n = 0;
    int pipes = 0;
    i64 ready = 0;
    for (i64 i = 0; i < count; i++) {
      p[i].revents = 0;
      if (p[i].fd < 0) continue;
      if (is_socket(p[i].fd)) {
        polled[n].fd = handles[p[i].fd];
        polled[n].events = (i16)(((p[i].events & 1) ? 0x100 : 0) | ((p[i].events & 4) ? 0x10 : 0));
        polled[n].revents = 0;
        n++;
      } else {
        p[i].revents = other_ready(p[i].fd, p[i].events);
        if (p[i].revents) ready++;
        else pipes = 1;
      }
    }
    i64 spent = (i64)(imp_GetTickCount64() - start);
    i64 left = limit < 0 ? -1 : (limit > spent ? limit - spent : 0);
    i32 wait = ready ? 0 : pipes ? (left == 0 ? 0 : 1) : (i32)(left > 0x7FFFFFFF ? 0x7FFFFFFF : left);
    /* WSAPoll may not tell of a connect that failed: while a socket waits to
       be written to, it is asked of select's exceptions between short waits
       (which leaves its SO_ERROR for the program). */
    int writers = 0;
    for (i64 i = 0; i < count; i++) if (p[i].fd >= 0 && is_socket(p[i].fd) && (p[i].events & 4)) writers = 1;
    if (writers && (wait < 0 || wait > 5)) wait = 5;
    if (n) {
      i32 r = imp_WSAPoll(polled, n, wait);
      if (r < 0) return wsa_fail();
      u32 k = 0;
      for (i64 i = 0; i < count; i++) {
        if (p[i].fd < 0 || !is_socket(p[i].fd)) continue;
        i16 w = polled[k++].revents, got = 0;
        if (w & 0x300) got |= 1;               /* POLLRDNORM, POLLRDBAND: POLLIN */
        if (w & 0x10) got |= 4;                /* POLLWRNORM: POLLOUT */
        if (w & 0x1) got |= 8;                 /* POLLERR */
        if (w & 0x2) got |= 0x10;              /* POLLHUP */
        if (w & 0x4) got |= 0x20;              /* POLLNVAL */
        if (!got && (p[i].events & 4)) {
          u64 except[2] = {1, handles[p[i].fd]};   /* fd_set: one socket */
          i32 zero[2] = {0, 0};
          if (imp_select(0, 0, 0, except, zero) == 1) got = 4 | 8;   /* POLLOUT | POLLERR */
        }
        p[i].revents = got;
        if (got) ready++;
      }
    } else if (!ready && wait > 0) {
      i64 pause[2] = {0, 1000000};             /* a millisecond */
      if (!pipes) { pause[0] = wait / 1000; pause[1] = (wait % 1000) * 1000000; }
      wait_for(pause);
    }
    if (ready) return ready;
    if (limit >= 0 && (i64)(imp_GetTickCount64() - start) >= limit) return 0;
  }
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
  region_add((u64)m, (u64)length);
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
  region_add((u64)m, (u64)grown);
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
  /* What the target is, is asked from the link's directory, where a
     relative one is resolved (as Go's os.Symlink joins them). */
  const u16 *probe = wpath1;
  static u16 wprobe[32768];
  if (wpath1[0] != '\\' && !(wpath1[0] && wpath1[1] == ':')) {
    u64 cut = 0, n = 0, m = 0;
    for (; wpath2[n]; n++) if (wpath2[n] == '\\' || wpath2[n] == '/') cut = n + 1;
    while (wpath1[m]) m++;
    if (cut + m < 32768) {
      for (u64 i = 0; i < cut; i++) wprobe[i] = wpath2[i];
      for (u64 i = 0; i <= m; i++) wprobe[cut + i] = wpath1[i];
      probe = wprobe;
    }
  }
  u32 attributes = imp_GetFileAttributesW(probe);
  u32 flags = 2 | ((attributes != 0xFFFFFFFF && (attributes & 0x10)) ? 1 : 0);
  return imp_CreateSymbolicLinkW(wpath2, wpath1, flags) ? 0 : fail();
}

/* stat and lstat of a path, as Go's os.Stat and os.Lstat: a link is
   followed (the file it names, opened) or told as one, of no size. */
static i64 sys_stat_path(i64 path, i64 st, int follow) {
  u8 data[36], found[592], info[52];
  if (!wide((const char *)path, wpath1)) return -ENOENT;
  commit_range((void *)st, 144);
  if (!imp_GetFileAttributesExW(wpath1, 0, data)) return fail();
  int link = 0;
  if (*(u32 *)data & 0x400) {                   /* FILE_ATTRIBUTE_REPARSE_POINT */
    /* Its tag, where a directory's entry gives it: a symbolic link or a
       mount point (a junction). */
    u64 h = imp_FindFirstFileW(wpath1, found);
    if (h != (u64)-1) {
      u32 tag = *(u32 *)(found + 36);
      link = tag == 0xA000000C || tag == 0xA0000003;
      imp_FindClose(h);
    }
  }
  if (link && follow) {
    /* No access asked, shared with all, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS. */
    u64 h = imp_CreateFileW(wpath1, 0, 7, 0, 3, 0x02000000, 0);
    if (h == (u64)-1) return fail();
    i32 ok = imp_GetFileInformationByHandle(h, info);
    if (!ok) { i64 r = fail(); imp_CloseHandle(h); return r; }
    imp_CloseHandle(h);
    memcpy(data, info, 28);
    *(u32 *)(data + 28) = *(u32 *)(info + 32);
    *(u32 *)(data + 32) = *(u32 *)(info + 36);
    link = 0;
  }
  u64 size = link ? 0 : ((u64)*(u32 *)(data + 28) << 32) | *(u32 *)(data + 32);
  if (link) *(u32 *)data &= ~0x10u;             /* a link to a directory is a link */
  fill_stat((void *)st, data, size);
  if (link) *(u32 *)((u8 *)st + 24) = 0120666;  /* S_IFLNK */
  return 0;
}

/* unlink, as the file's half of Go's os.Remove on Windows: a link to a
   directory is removed as a directory is, and a file that may not be
   written is made writable and deleted. */
static i64 sys_unlink(i64 path) {
  if (!wide((const char *)path, wpath1)) return -ENOENT;
  if (imp_DeleteFileW(wpath1)) return 0;
  u32 why = imp_GetLastError();
  u32 a = imp_GetFileAttributesW(wpath1);
  if (a != 0xFFFFFFFF) {
    if ((a & 0x410) == 0x410 && imp_RemoveDirectoryW(wpath1)) return 0;
    if (!(a & 0x10) && (a & 1) && imp_SetFileAttributesW(wpath1, (a & ~1u) ? (a & ~1u) : 0x80)) {
      if (imp_DeleteFileW(wpath1)) return 0;
      why = imp_GetLastError();
      imp_SetFileAttributesW(wpath1, a);
    }
  }
  imp_SetLastError(why);
  return fail();
}

/* readlink(path, buffer, size), as Go's os.Readlink: where the link's
   reparse point says it leads, without the \??\ of an absolute one. */
static i64 sys_readlink(i64 path, i64 buffer, i64 size) {
  static u8 point[16384];
  if (!wide((const char *)path, wpath1)) return -ENOENT;
  if (size <= 0) return -EINVAL;
  /* No access asked, shared with all, OPEN_EXISTING,
     FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS. */
  u64 h = imp_CreateFileW(wpath1, 0, 7, 0, 3, 0x02200000, 0);
  if (h == (u64)-1) return fail();
  u32 got = 0;
  i32 ok = imp_DeviceIoControl(h, 0x900A8, 0, 0, point, sizeof point, &got, 0);   /* FSCTL_GET_REPARSE_POINT */
  if (!ok) { i64 r = fail(); imp_CloseHandle(h); return r == -EIO ? -EINVAL : r; }
  imp_CloseHandle(h);
  u32 tag = *(u32 *)point;
  u16 *names;
  int relative = 0;
  if (tag == 0xA000000C) { names = (u16 *)(point + 20); relative = *(u32 *)(point + 16) & 1; }
  else if (tag == 0xA0000003) names = (u16 *)(point + 16);
  else return -EINVAL;
  u16 *name = names + *(u16 *)(point + 8) / 2;
  i32 n = *(u16 *)(point + 10) / 2;
  if (!relative && n >= 4 && name[0] == '\\' && name[1] == '?' && name[2] == '?' && name[3] == '\\') {
    name += 4;
    n -= 4;
    /* \??\UNC\host\share is \\host\share. */
    if (n >= 4 && name[0] == 'U' && name[1] == 'N' && name[2] == 'C' && name[3] == '\\') {
      name += 2;
      n -= 2;
      name[0] = '\\';
    }
  }
  if (!n) return 0;
  commit_range((void *)buffer, (u64)size);
  i32 m = imp_WideCharToMultiByte(65001, 0, name, n, (char *)buffer, (i32)(size > 0x7FFFFFFF ? 0x7FFFFFFF : size), 0, 0);
  return m > 0 ? m : -ENAMETOOLONG;
}

/* utimensat(dir, path, times, flags): the access and write times, each
   the time given, now (no times, or UTIME_NOW) or left (UTIME_OMIT). */
static i64 sys_utimens(i64 path, i64 times) {
  if (!wide((const char *)path, wpath1)) return -ENOENT;
  u64 now, set[2];
  const u64 *use[2] = {0, 0};
  imp_GetSystemTimeAsFileTime(&now);
  if (times) commit_range((void *)times, 32);
  for (int k = 0; k < 2; k++) {
    i64 seconds = times ? ((i64 *)times)[2 * k] : 0, nanos = times ? ((i64 *)times)[2 * k + 1] : 0x3FFFFFFF;
    if (nanos == 0x3FFFFFFE) continue;
    set[k] = nanos == 0x3FFFFFFF ? now : (u64)(seconds * 10000000 + nanos / 100 + 116444736000000000LL);
    use[k] = &set[k];
  }
  /* FILE_WRITE_ATTRIBUTES, shared with all, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS. */
  u64 h = imp_CreateFileW(wpath1, 0x100, 7, 0, 3, 0x02000000, 0);
  if (h == (u64)-1) return fail();
  i64 r = imp_SetFileTime(h, 0, use[0], use[1]) ? 0 : fail();
  imp_CloseHandle(h);
  return r;
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
  if (copying) { handles[fd] = 0; socket_fd[fd] = 0; return; }   /* the parent's */
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

/* --- Local time ----------------------------------------------------------

   Go's time.Local on Windows (time/zoneinfo_windows.go): the system's zone
   from GetTimeZoneInformation, one zone when it has no summer time, else
   two and their transitions for the hundred years around now (pseudoUnix),
   the abbreviations from Go's table of Windows zone names (generated from
   the pinned toolchain's zoneinfo_abbrs_windows.go: abbrs.h), else from the
   table under the zone's English name in the registry, else the capitals
   of its name. Pseudo call 1000105 (Date.dl) is Location.lookup. */

#include "abbrs.h"

static struct {
  int ready, zones;
  i64 offset[2];
  int dst[2];
  char name[2][64];
  u32 length[2];
  int count;
  i64 when[400];
  u8 index[400];
} local;

static int same_name(const u16 *w, const char *a) {
  for (; *a; w++, a++) if (*w != (u16)(u8)*a) return 0;
  return *w == 0;
}

static void caps(const u16 *w, int z) {
  u32 n = 0;
  for (; *w && n < 63; w++) if (*w >= 'A' && *w <= 'Z') local.name[z][n++] = (char)*w;
  local.name[z][n] = 0;
  local.length[z] = n;
}

static void named(int z, const char *a) {
  u32 n = 0;
  for (; a[n] && n < 63; n++) local.name[z][n] = a[n];
  local.name[z][n] = 0;
  local.length[z] = n;
}

/* Go's table, by a name. */
static int from_table(const u16 *name) {
  for (u32 k = 0; k < sizeof abbrs / sizeof abbrs[0]; k++)
    if (same_name(name, abbrs[k][0])) {
      named(0, abbrs[k][1]);
      named(1, abbrs[k][2]);
      return 1;
    }
  return 0;
}

static int same_wide(const u16 *a, const u16 *b) {
  for (; *a && *a == *b; a++, b++) {}
  return *a == *b;
}

/* toEnglishName: the key under Time Zones whose standard and summer names
   (MUI_Std and MUI_Dlt, else Std and Dlt) are these, in name. */
static int english(const u16 *std, const u16 *dlt, u16 *name) {
  u64 zones;
  if (imp_RegOpenKeyExW(0xFFFFFFFF80000002ull, u"SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Time Zones", 0, 0x20019, &zones)) return 0;
  int found = 0;
  for (u32 i = 0; !found; i++) {
    u32 n = 256;
    if (imp_RegEnumKeyExW(zones, i, name, &n, 0, 0, 0, 0)) break;
    u64 key;
    if (imp_RegOpenKeyExW(zones, name, 0, 0x20019, &key)) continue;
    u16 a[256], b[256];
    u32 an = 0, bn = 0;
    int ok = !imp_RegLoadMUIStringW(key, u"MUI_Std", a, sizeof a, &an, 0, 0) && !imp_RegLoadMUIStringW(key, u"MUI_Dlt", b, sizeof b, &bn, 0, 0);
    if (!ok) {
      u32 type, size = sizeof a;
      ok = !imp_RegQueryValueExW(key, u"Std", 0, &type, a, &size);
      a[255] = 0;
      size = sizeof b;
      ok = ok && !imp_RegQueryValueExW(key, u"Dlt", 0, &type, b, &size);
      b[255] = 0;
    }
    if (ok && same_wide(a, std) && (same_wide(b, dlt) || same_wide(dlt, std))) found = 1;
    imp_RegCloseKey(key);
  }
  imp_RegCloseKey(zones);
  return found;
}

static i64 days_from_civil(i64 y, i64 m, i64 d) {
  y -= m <= 2;
  i64 era = (y >= 0 ? y : y - 399) / 400;
  i64 yoe = y - era * 400;
  i64 doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
  i64 doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
  return era * 146097 + doe - 719468;
}

static int days_in(int m, i64 y) {
  static const u8 n[12] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
  if (m == 2 && ((y % 4 == 0 && y % 100 != 0) || y % 400 == 0)) return 29;
  return n[m - 1];
}

/* pseudoUnix: the moment in year the SYSTEMTIME rule d names (the day-th
   weekday of the month, 5 the last), as seconds since 1970 read as UTC. */
static i64 pseudo_unix(i64 year, const u16 *d) {
  i64 first = days_from_civil(year, d[1], 1);
  i64 weekday = ((first % 7) + 11) % 7;          /* 1970-01-01 was a Thursday */
  i64 day = 1;
  i64 i = (i64)d[2] - weekday;
  if (i < 0) i += 7;
  day += i;
  i64 week = (i64)d[3] - 1;
  if (week < 4) day += week * 7;
  else {
    day += 4 * 7;
    if (day > days_in(d[1], year)) day -= 7;
  }
  return (first + day - 1) * 86400 + (i64)d[4] * 3600 + (i64)d[5] * 60 + d[6];
}

static void local_init(void) {
  u8 info[172];
  memset(info, 0, sizeof info);
  local.ready = 1;
  if (imp_GetTimeZoneInformation(info) == 0xFFFFFFFF) {
    local.zones = 0;
    return;
  }
  i32 bias = *(i32 *)info, standard_bias = *(i32 *)(info + 84), daylight_bias = *(i32 *)(info + 168);
  const u16 *std_name = (u16 *)(info + 4), *dst_name = (u16 *)(info + 88);
  u16 *std_date = (u16 *)(info + 68), *dst_date = (u16 *)(info + 152);
  /* The names may fill their 32 units without an end. */
  u16 std[33], dst[33];
  memcpy(std, std_name, 64); std[32] = 0;
  memcpy(dst, dst_name, 64); dst[32] = 0;
  if (!from_table(std)) {
    u16 key[256];
    if (!english(std, dst, key) || !from_table(key)) { caps(std, 0); caps(dst, 1); }
  }
  local.dst[0] = 0;
  local.dst[1] = 1;
  if (std_date[1] == 0) {
    local.zones = 1;
    local.offset[0] = -(i64)bias * 60;
    local.count = 1;
    local.when[0] = -9223372036854775807LL - 1;
    local.index[0] = 0;
    return;
  }
  local.zones = 2;
  local.offset[0] = -(i64)(bias + standard_bias) * 60;
  local.offset[1] = -(i64)(bias + daylight_bias) * 60;
  u16 *d0 = std_date, *d1 = dst_date;
  int i0 = 0, i1 = 1;
  if (d0[1] > d1[1]) { u16 *t = d0; d0 = d1; d1 = t; i0 = 1; i1 = 0; }
  u16 now[8];
  imp_GetSystemTime(now);
  i64 year = now[0];
  int n = 0;
  for (i64 y = year - 100; y < year + 100; y++) {
    local.when[n] = pseudo_unix(y, d0) - local.offset[i1];
    local.index[n++] = (u8)i0;
    local.when[n] = pseudo_unix(y, d1) - local.offset[i0];
    local.index[n++] = (u8)i1;
  }
  local.count = n;
}

/* Location.lookup of Local at sec: out gets the offset, where its span
   starts and ends, and the abbreviation's address and length. */
static i64 local_lookup(i64 sec, i64 out) {
  if (!local.ready) local_init();
  i64 *o = (i64 *)out;
  commit_range(o, 40);
  const i64 alpha = -9223372036854775807LL - 1, omega = 9223372036854775807LL;
  if (local.zones == 0) {
    static char utc[] = "UTC";
    o[0] = 0; o[1] = alpha; o[2] = omega; o[3] = (i64)utc; o[4] = 3;
    return 0;
  }
  if (local.zones == 1) {
    o[0] = local.offset[0]; o[1] = alpha; o[2] = omega;
    o[3] = (i64)local.name[0]; o[4] = local.length[0];
    return 0;
  }
  int z;
  i64 start, end = omega;
  if (sec < local.when[0]) {
    /* lookupFirstZone: the first zone is used by the transitions; when the
       first is to summer time, the standard zone before it, else the first
       standard zone. */
    z = 0;
    if (local.dst[local.index[0]]) {
      for (int k = local.index[0] - 1; k >= 0; k--) if (!local.dst[k]) { z = k; break; }
    }
    start = alpha;
    end = local.when[0];
  } else {
    int lo = 0, hi = local.count;
    while (hi - lo > 1) {
      int m = (lo + hi) / 2;
      if (sec < local.when[m]) { end = local.when[m]; hi = m; } else lo = m;
    }
    z = local.index[lo];
    start = local.when[lo];
  }
  o[0] = local.offset[z]; o[1] = start; o[2] = end;
  o[3] = (i64)local.name[z]; o[4] = local.length[z];
  return 0;
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

/* --- A copy of the program (fork) ---------------------------------------

   Windows has no fork. The library forks for one thing: a failing process
   has a copy of the program fail in earnest, its standard error on a pipe,
   for the trace (Process._trace); the copy then exits. Here fork returns 0
   and the program goes on as the copy, with the parent kept: the CONTEXT of
   the call, the descriptor table, the stack it runs on from just below its
   stack pointer up (copied whole: Windows writes its exception records on
   the stack that faults), and every other page of the program's memory,
   made read-only and copied the first time the copy writes to it
   (copy_fault, and commit_range for what the layer writes). Pages the copy
   commits are decommitted after, as free memory must be zero. When the
   copy exits, all that is put back and fork returns in the parent, the copy
   a process that has ended with its status (wait4). */

#define COPY_PID 0x7FFF0001
static u8 copy_context[0x4D0] __attribute__((aligned(16)));
static u64 copy_handles[FDS];
static u8 copy_sockets[FDS];
static u32 copy_regions;
static i64 copy_status = -1;
/* Pages saved (address, then 4096 bytes), ranges made read-only (address,
   size) and ranges committed (address, size), in one VirtualAlloc'd store. */
#define COPY_STORE (256u << 20)
static u8 *copy_store;
static u64 copy_used;
static u64 *protected_ranges, protected_count;
static u64 *committed_ranges, committed_count;
#define RANGES 65536
static u64 stack_low, stack_high;
static u8 *stack_copy;
static u8 *resume_stack;

void region_add(u64 at, u64 size) {
  if (region_count < REGIONS) {
    regions[region_count][0] = at;
    regions[region_count][1] = size;
    region_count++;
  }
}

static int region_index(u64 a) {
  for (u32 i = 0; i < region_count; i++)
    if (a >= regions[i][0] && a < regions[i][0] + regions[i][1]) return (int)i;
  return -1;
}

static int is_protected(u64 page) {
  for (u64 i = 0; i < protected_count; i++)
    if (page >= protected_ranges[2 * i] && page < protected_ranges[2 * i] + protected_ranges[2 * i + 1]) return 1;
  return 0;
}

/* The page at page, saved and writable again; 0 when there is no room. */
static u64 store_committed;
static int save_page(u64 page) {
  if (copy_used + 8 + 4096 > COPY_STORE) return 0;
  if (copy_used + 8 + 4096 > store_committed) {
    if (!imp_VirtualAlloc(copy_store + store_committed, 1 << 20, 0x1000, 4)) return 0;
    store_committed += 1 << 20;
  }
  u8 *to = copy_store + copy_used;
  *(u64 *)to = page;
  memcpy(to + 8, (void *)page, 4096);
  copy_used += 8 + 4096;
  u32 old;
  imp_VirtualProtect((void *)page, 4096, 4, &old);
  return 1;
}

static int page_saved(u64 page) {
  for (u64 at = 0; at < copy_used; at += 8 + 4096)
    if (*(u64 *)(copy_store + at) == page) return 1;
  return 0;
}

int copy_fault(u8 *record);

/* What the copy writes, from the layer: saved first. */
void copy_write(u64 at, u64 length) {
  if (!copying || !length) return;
  for (u64 page = at & ~4095ull; page < at + length; page += 4096) {
    if (is_protected(page)) { if (!page_saved(page)) save_page(page); continue; }
    /* Reserved memory the layer is about to commit: committed here, to be
       decommitted after. */
    u8 record[0x30];
    *(u64 *)(record + 0x28) = page;
    copy_fault(record);
  }
}

/* An access violation while a copy runs (the EXCEPTION_RECORD): a write to
   a page kept for the parent saves it; a touch of reserved memory commits
   it, to be decommitted after. 1 when it is handled. */
int copy_fault(u8 *record) {
  if (!copying) return 0;
  u64 address = *(u64 *)(record + 0x28);
  u64 page = address & ~4095ull;
  if (is_protected(page)) {
    if (page_saved(page)) return 0;
    return save_page(page);
  }
  int r = region_index(address);
  if (r < 0) return 0;
  u8 info[48];
  if (!imp_VirtualQuery((void *)page, info, sizeof info)) return 0;
  if (*(u32 *)(info + 32) != 0x2000) return 0;              /* MEM_RESERVE */
  u64 end = regions[r][0] + regions[r][1];
  u64 size = (end - page) < 65536 ? ((end - page + 4095) & ~4095ull) : 65536;
  if (!imp_VirtualAlloc((void *)page, size, 0x1000, 4)) return 0;
  if (committed_count < RANGES) {
    committed_ranges[2 * committed_count] = page;
    committed_ranges[2 * committed_count + 1] = size;
    committed_count++;
  }
  return 1;
}

/* What a copy writes to a pipe. The program reads the pipe once the copy
   has ended (it is the one thread), so a copy that wrote more than the
   pipe holds would wait for ever: what it writes is kept, and written by
   a thread of its own once the program runs again, to a duplicate of the
   handle that it closes after (the reader's end of file). One pipe, the
   first the copy writes to that is not the program's standard output or
   errors, which someone else reads; the first 16 bytes kept are the
   handle and the length. */
#define SPILL_ROOM (1ull << 32)
static u8 *spill;
static u64 spill_handle, spill_used, spill_committed, fork_standard[3];

static W u32 spill_writer(void *given) {
  u8 *kept = given, *at = kept + 16;
  u64 h = *(u64 *)kept, left = *(u64 *)(kept + 8);
  while (left) {
    u32 done = 0;
    if (!imp_WriteFile(h, at, left > 65536 ? 65536 : (u32)left, &done, 0) || !done) break;
    at += done;
    left -= done;
  }
  imp_CloseHandle(h);
  imp_VirtualFree(kept, 0, 0x8000);
  return 0;
}

static i64 spill_write(i64 fd, i64 data, i64 n) {
  if (fd < 0 || fd >= FDS || is_socket(fd) || n < 0) return NOT_MINE;
  u64 h = handle_of((u64)fd);
  if (!h || imp_GetFileType(h) != 3) return NOT_MINE;        /* FILE_TYPE_PIPE */
  if (spill_handle && spill_handle != h) return NOT_MINE;
  for (int k = 0; k < 3; k++) if (h == fork_standard[k]) return NOT_MINE;
  if (!spill) {
    if (!(spill = imp_VirtualAlloc(0, SPILL_ROOM, 0x2000, 4))) return NOT_MINE;
    spill_used = 16;
    spill_committed = 0;
  }
  if (spill_used + (u64)n > SPILL_ROOM) return -ENOSPC;
  while (spill_used + (u64)n > spill_committed) {
    if (!imp_VirtualAlloc(spill + spill_committed, 1 << 20, 0x1000, 4)) return -ENOMEM;
    spill_committed += 1 << 20;
  }
  spill_handle = h;
  commit_range((void *)data, (u64)n);
  memcpy(spill + spill_used, (void *)data, (u64)n);
  spill_used += (u64)n;
  return n;
}

/* The copy ends: what it wrote goes to its pipe from a thread. */
static void spill_send(void) {
  if (spill) {
    u64 me = imp_GetCurrentProcess(), h = 0, thread = 0;
    if (imp_DuplicateHandle(me, spill_handle, me, &h, 0, 0, 2)) {
      *(u64 *)spill = h;
      *(u64 *)(spill + 8) = spill_used - 16;
      thread = imp_CreateThread(0, 0, spill_writer, spill, 0, 0);
      if (thread) imp_CloseHandle(thread);
      else { imp_CloseHandle(h); imp_VirtualFree(spill, 0, 0x8000); }
    } else imp_VirtualFree(spill, 0, 0x8000);
  }
  spill = 0;
  spill_handle = spill_used = spill_committed = 0;
}

/* fork: the copy starts (0), or -errno. */
static i64 sys_fork(unsigned char *c) {
  if (copying) return -11;                                   /* EAGAIN */
  if (!copy_store && !(copy_store = imp_VirtualAlloc(0, COPY_STORE, 0x2000, 4))) return -12;
  if (!protected_ranges) {
    protected_ranges = imp_VirtualAlloc(0, RANGES * 16, 0x3000, 4);
    committed_ranges = imp_VirtualAlloc(0, RANGES * 16, 0x3000, 4);
    if (!protected_ranges || !committed_ranges) return -12;
  }
  copy_used = 0;
  store_committed = 0;
  for (u64 k = 0; k < 3; k++) fork_standard[k] = handle_of(k);
  protected_count = committed_count = 0;
  memcpy(copy_context, c, sizeof copy_context);
  memcpy(copy_handles, handles, sizeof copy_handles);
  memcpy(copy_sockets, socket_fd, sizeof copy_sockets);
  copy_regions = region_count;
  /* The stack it runs on, from just below its pointer to its region's end. */
  u64 rsp = *(u64 *)(c + 0x98);
  int s = region_index(rsp);
  /* The whole stack, not only what lies above its pointer: the copy goes
     deeper than where it was made (the failure passes on, the trace is
     written, each call of the layer leaves Windows' records there), and a
     page of the stack kept read-only could not take the record of its own
     fault. Pages a deeper call left committed below the pointer are
     written as they are. */
  stack_low = s < 0 ? ((rsp - 4096) & ~4095ull) : regions[s][0];
  stack_high = s < 0 ? ((rsp + 65536) & ~4095ull) : regions[s][0] + regions[s][1];
  u64 stack_size = stack_high - stack_low;
  stack_copy = imp_VirtualAlloc(0, stack_size, 0x2000, 4);
  if (!stack_copy) return -12;
  /* Only what is committed and written of it is there to keep (not the
     guard pages below, which a read would take for a growing stack). */
  for (u64 a = stack_low; a < stack_high;) {
    u8 info[48];
    if (!imp_VirtualQuery((void *)a, info, sizeof info)) break;
    u64 base = *(u64 *)info, size = *(u64 *)(info + 24);
    u64 end = base + size > stack_high ? stack_high : base + size;
    if (*(u32 *)(info + 32) == 0x1000 && *(u32 *)(info + 36) == 4) {
      if (!imp_VirtualAlloc(stack_copy + (a - stack_low), end - a, 0x1000, 4)) {
        imp_VirtualFree(stack_copy, 0, 0x8000);
        return -12;
      }
      memcpy(stack_copy + (a - stack_low), (void *)a, end - a);
    }
    a = end;
  }
  /* Every other committed, writable page of the program's memory. */
  for (u32 i = 0; i < region_count; i++) {
    for (u64 a = regions[i][0], e = regions[i][0] + regions[i][1]; a < e;) {
      u8 info[48];
      if (!imp_VirtualQuery((void *)a, info, sizeof info)) break;
      u64 base = *(u64 *)info, size = *(u64 *)(info + 24);
      u64 end = base + size > e ? e : base + size;
      if (*(u32 *)(info + 32) == 0x1000 && *(u32 *)(info + 36) == 4) {
        /* Not the stack kept whole. */
        u64 lo = a, hi = end;
        u64 parts[2][2] = {{lo, hi < stack_low ? hi : stack_low}, {lo > stack_high ? lo : stack_high, hi}};
        for (int k = 0; k < 2; k++) {
          if (parts[k][0] >= parts[k][1] || protected_count >= RANGES) continue;
          u32 old;
          if (imp_VirtualProtect((void *)parts[k][0], parts[k][1] - parts[k][0], 2, &old)) {
            protected_ranges[2 * protected_count] = parts[k][0];
            protected_ranges[2 * protected_count + 1] = parts[k][1] - parts[k][0];
            protected_count++;
          }
        }
      }
      a = end;
    }
  }
  copying = 1;
  return 0;
}

/* The copy exits with status: the parent is put back and its fork returns
   the copy's number. */
static i64 copy_exit(unsigned char *c, i64 status) {
  spill_send();
  /* Descriptors: the parent's table; what the copy opened is closed. */
  for (int fd = 0; fd < FDS; fd++) {
    if (!handles[fd]) continue;
    int kept_one = 0;
    for (int k = 0; k < FDS; k++) if (copy_handles[k] == handles[fd]) { kept_one = 1; break; }
    if (!kept_one) { if (socket_fd[fd]) imp_closesocket(handles[fd]); else imp_CloseHandle(handles[fd]); }
  }
  memcpy(handles, copy_handles, sizeof copy_handles);
  memcpy(socket_fd, copy_sockets, sizeof copy_sockets);
  /* Memory: the saved pages, the protection, the stack; what was committed
     is decommitted, what was mapped is let go. */
  for (u64 i = 0; i < protected_count; i++) {
    u32 old;
    imp_VirtualProtect((void *)protected_ranges[2 * i], protected_ranges[2 * i + 1], 4, &old);
  }
  for (u64 at = 0; at < copy_used; at += 8 + 4096)
    memcpy((void *)*(u64 *)(copy_store + at), copy_store + at + 8, 4096);
  for (u64 i = 0; i < committed_count; i++)
    imp_VirtualFree((void *)committed_ranges[2 * i], committed_ranges[2 * i + 1], 0x4000);
  for (u32 i = copy_regions; i < region_count; i++)
    imp_VirtualFree((void *)regions[i][0], 0, 0x8000);
  region_count = copy_regions;
  if (store_committed) imp_VirtualFree(copy_store, store_committed, 0x4000);
  copying = 0;
  copy_status = status & 0xFF;
  /* The stack is put back once Windows is done with this exception, whose
     records lie on it: the thread goes on in copy_resume, on a stack of the
     layer's (the handler moves RIP past the call it took this for). */
  if (!resume_stack && !(resume_stack = imp_VirtualAlloc(0, 65536, 0x3000, 4))) imp_ExitProcess(70);
  *(u64 *)(c + 0xF8) = (u64)copy_resume - 2;
  *(u64 *)(c + 0x98) = (u64)resume_stack + 65536;
  return 0;
}

/* On the layer's stack: the parent's stack as it was, then the parent at
   its fork, which gives the copy's number. */
void copy_resume_c(void) {
  /* What was kept of the stack: the committed parts of the copy of it. */
  for (u64 a = 0, n = stack_high - stack_low; a < n;) {
    u8 info[48];
    if (!imp_VirtualQuery(stack_copy + a, info, sizeof info)) break;
    u64 base = *(u64 *)info, size = *(u64 *)(info + 24);
    u64 end = base + size - (u64)stack_copy > n ? n : base + size - (u64)stack_copy;
    if (*(u32 *)(info + 32) == 0x1000) memcpy((void *)(stack_low + a), stack_copy + a, end - a);
    a = end;
  }
  imp_VirtualFree(stack_copy, 0, 0x8000);
  u8 *c = copy_context;
  u64 rip = *(u64 *)(c + 0xF8) + 2;
  *(u64 *)(c + 0xF8) = rip;
  *(u64 *)(c + 0x78) = COPY_PID;                 /* RAX */
  *(u64 *)(c + 0x80) = rip;                      /* RCX */
  *(u64 *)(c + 0xD0) = *(u32 *)(c + 0x44);       /* R11: EFlags */
  /* CONTEXT_AMD64 | CONTROL | INTEGER | FLOATING_POINT: the extended state
     the handler's CONTEXT may name is not in this copy of it. */
  *(u32 *)(c + 0x30) = 0x10000B;
  imp_RtlRestoreContext(c, 0);
}

/* --- Stacks ---------------------------------------------------------------

   A stack (an anonymous mapping with MAP_STACK, which a Windows program gives
   its main stack and each process's) is reserved whole and grows as
   Windows grows a thread's stack: its top 64 KiB committed, below them a
   band of guard pages, which the kernel commits when one is touched and
   moves down, as long as the TEB names the stack (StackBase, StackLimit,
   DeallocationStack). Windows writes the record of an exception on the
   stack that faulted, so the stack could not grow through the handler.
   The program sets the TEB when it starts on its stack and when it
   switches stacks (nc_stack_init, Process.__switch); a stack's first page
   keeps its limit and top while another runs: its first word the limit
   (the lowest committed address), its second the top. The stack guarantee
   (64 KiB, set at the start) keeps the band of guard pages that deep, so a
   frame of up to 64 KiB does not step over it; a function with a larger
   frame touches its pages from the top down first (nc_guard). */

#define STACK_TOP (64 << 10)
#define STACK_GUARD (68 << 10)

static i64 sys_mmap_anonymous(i64 size, i64 flags) {
  u64 n = ((u64)size + 4095) & ~4095ull;
  if (!n) return -EINVAL;
  if (n > 0x100000000ull) {
    void *m = imp_VirtualAlloc(0, n, 0x2000, 4);                 /* MEM_RESERVE */
    if (!m) return -ENOMEM;
    region_add((u64)m, n);
    return (i64)m;
  }
  if ((flags & 0x20000) && n >= (256 << 10)) {                   /* MAP_STACK */
    u8 *m = imp_VirtualAlloc(0, n, 0x2000, 4);
    if (!m) return -ENOMEM;
    u64 top = (u64)m + n, limit = top - STACK_TOP;
    /* PAGE_READWRITE | PAGE_GUARD for the band. */
    if (!imp_VirtualAlloc((void *)limit, STACK_TOP, 0x1000, 4) || !imp_VirtualAlloc((void *)(limit - STACK_GUARD), STACK_GUARD, 0x1000, 0x104)
        || !imp_VirtualAlloc(m, 4096, 0x1000, 4)) {
      imp_VirtualFree(m, 0, 0x8000);
      return -ENOMEM;
    }
    ((u64 *)m)[0] = limit;
    ((u64 *)m)[1] = top;
    region_add((u64)m, n);
    return (i64)m;
  }
  void *m = imp_VirtualAlloc(0, n, 0x3000, 4);
  if (!m) return -ENOMEM;
  region_add((u64)m, n);
  return (i64)m;
}

/* --- Processes -------------------------------------------------------- */

/* The processes started (pid, handle); a pid is looked up here for wait4
   and kill. */
#define CHILDREN 256
static u32 child_pid[CHILDREN];
static u64 child_handle[CHILDREN];
static u64 child_timer[CHILDREN];

/* A timer of the timer queue ends the process it was set for (flag 16 of
   spawn); it runs on a thread of the pool, and touches nothing but the
   process. */
static W void end_child(void *process, u8 fired) {
  (void)fired;
  imp_TerminateProcess((u64)process, 1);
}

static int child_of(i64 pid) {
  for (int i = 0; i < CHILDREN; i++)
    if (child_handle[i] && child_pid[i] == (u32)pid) return i;
  return -1;
}

/* What is built for CreateProcessW: the command line, the environment
   block and the directory, in UTF-16; and UTF-8 room to build them in. */
#define SPAWN_UNITS (1 << 23)
static u16 *spawn_wide;
static char *spawn_text;

/* Go's syscall.appendEscapeArg: s as one argument of a command line. */
static i64 escape_arg(char *b, i64 at, i64 room, const char *s) {
  i64 n = 0;
  int needs_backslash = 0, has_space = 0;
  for (; s[n]; n++) {
    if (s[n] == '"' || s[n] == '\\') needs_backslash = 1;
    if (s[n] == ' ' || s[n] == '\t') has_space = 1;
  }
  if (at + 2 * n + 4 >= room) return -1;
  if (n == 0) { b[at++] = '"'; b[at++] = '"'; return at; }
  if (!needs_backslash && !has_space) { memcpy(b + at, s, (u64)n); return at + n; }
  if (!needs_backslash) {
    b[at++] = '"'; memcpy(b + at, s, (u64)n); at += n; b[at++] = '"';
    return at;
  }
  if (has_space) b[at++] = '"';
  i64 slashes = 0;
  for (i64 i = 0; i < n; i++) {
    char c = s[i];
    if (c == '\\') slashes++;
    else if (c == '"') { for (; slashes > 0; slashes--) b[at++] = '\\'; b[at++] = '\\'; }
    else slashes = 0;
    b[at++] = c;
  }
  if (has_space) { for (; slashes > 0; slashes--) b[at++] = '\\'; b[at++] = '"'; }
  return at;
}

static int same_key(const char *a, const char *b) {
  /* The names of two "key=value" entries, in either case (dedupEnvCase). */
  i64 i = 0;
  if (a[0] == '=' && b[0] == '=') i = 1;
  for (;; i++) {
    char x = a[i], y = b[i];
    if (x >= 'A' && x <= 'Z') x += 32;
    if (y >= 'A' && y <= 'Z') y += 32;
    if (x != y) return 0;
    if (x == '=' || x == 0) return x == '=';
  }
}

/* spawn (pseudo call 1000104): the program at path with the arguments argv
   and the environment envp (zero-ended lists of UTF-8 strings), in dir
   unless it is 0, as Go's os.StartProcess makes it on Windows. flags: 1 its
   input is a pipe (else NUL); 2 its errors go with its output, 4 to NUL,
   8 to the file named at out[0] (made anew), else where the program's own
   go; 16 it is ended after out[1] milliseconds; 32 its input, output and
   errors are the program's own (no pipes). out gets the descriptor its
   output is read from (-1 with 32) and the one its input is written to.
   The process's number, or -errno. */
static i64 sys_spawn(i64 path, i64 argv, i64 envp, i64 dir, i64 flags, i64 out) {
  i64 *given = (i64 *)out;
  commit_range(given, 16);
  const char *err_path = (flags & 8) ? (const char *)given[0] : 0;
  i64 kill_ms = (flags & 16) ? given[1] : 0;
  if (!spawn_wide && !(spawn_wide = imp_VirtualAlloc(0, SPAWN_UNITS * 2, 0x3000, 4))) return -ENOMEM;
  if (!spawn_text && !(spawn_text = imp_VirtualAlloc(0, SPAWN_UNITS, 0x3000, 4))) return -ENOMEM;
  char **args = (char **)argv, **env = (char **)envp;
  /* The command line. */
  i64 at = 0;
  for (i64 i = 0; args && args[i]; i++) {
    if (i) spawn_text[at++] = ' ';
    at = escape_arg(spawn_text, at, SPAWN_UNITS / 4, args[i]);
    if (at < 0) return -7;                     /* E2BIG */
  }
  spawn_text[at] = 0;
  u16 *line = spawn_wide;
  i32 n = imp_MultiByteToWideChar(65001, 0, spawn_text, -1, line, SPAWN_UNITS / 4);
  if (n <= 0) return -7;
  /* The environment: each name once, its last value (dedupEnvCase), and
     SYSTEMROOT, which Windows programs need (addCriticalEnv). */
  u16 *block = line + n;
  /* Room is kept after it for the name of a file for the errors. */
  if ((u64)n + 40000 > SPAWN_UNITS) return -7;
  u64 left = SPAWN_UNITS - (u64)n - 40000;
  u64 used = 0;
  int has_root = 0;
  for (i64 i = 0; env && env[i]; i++) {
    int later = 0;
    for (i64 j = i + 1; env[j]; j++) if (same_key(env[i], env[j])) { later = 1; break; }
    if (later) continue;
    if (same_key(env[i], "SYSTEMROOT=")) has_root = 1;
    if (left - used < 2) return -7;
    i32 m = imp_MultiByteToWideChar(65001, 0, env[i], -1, block + used, (i32)(left - used));
    if (m <= 0) return -7;
    used += (u64)m;
  }
  if (!has_root && left - used > 40000) {
    const char *name = "SYSTEMROOT=";
    u64 k = 0;
    for (; name[k]; k++) block[used + k] = (u16)name[k];
    u16 *value = block + used + k;
    u32 v = imp_GetEnvironmentVariableW(u"SYSTEMROOT", value, 32768);
    if (v) used += k + v + 1;
  }
  if (!used) block[used++] = 0;
  block[used++] = 0;
  /* The program's path and its directory. */
  if (!wide((const char *)path, wpath1)) return -ENOENT;
  u16 *directory = 0;
  if (dir) {
    if (!wide((const char *)dir, wpath2)) return -ENOENT;
    directory = wpath2;
  }
  /* The pipes, their child's ends inherited. */
  u64 sa[3] = {24, 0, 1};                      /* SECURITY_ATTRIBUTES, inherited */
  u64 out_read = 0, out_write = 0, in_read = 0, in_write = 0, null_in = 0, null_err = 0, err = 0;
  i64 r = 0;
  u64 me = imp_GetCurrentProcess();
  if (flags & 32) {
    /* The program's own three, inherited. */
    imp_DuplicateHandle(me, handle_of(0), me, &in_read, 0, 1, 2);
    imp_DuplicateHandle(me, handle_of(1), me, &out_write, 0, 1, 2);
    imp_DuplicateHandle(me, handle_of(2), me, &null_err, 0, 1, 2);
    err = null_err;
  } else {
  if (!imp_CreatePipe(&out_read, &out_write, sa, 0)) return fail();
  imp_SetHandleInformation(out_read, 1, 0);
  if (flags & 1) {
    if (!imp_CreatePipe(&in_read, &in_write, sa, 0)) { r = fail(); goto close; }
    imp_SetHandleInformation(in_write, 1, 0);
  } else {
    null_in = imp_CreateFileW(u"NUL", 0x80000000, 3, sa, 3, 0, 0);
    in_read = null_in;
  }
  if (flags & 2) err = out_write;
  else if (flags & 4) { null_err = imp_CreateFileW(u"NUL", 0x40000000, 3, sa, 3, 0, 0); err = null_err; }
  else if (flags & 8) {
    /* GENERIC_WRITE, sharing all, CREATE_ALWAYS. */
    u16 *name = block + used + 8;
    if (imp_MultiByteToWideChar(65001, 0, err_path, -1, name, 32768) <= 0) { r = -ENOENT; goto close; }
    null_err = imp_CreateFileW(name, 0x40000000, 7, sa, 2, 0x80, 0);
    if (null_err == (u64)-1) { null_err = 0; r = fail(); goto close; }
    err = null_err;
  } else {
    if (!imp_DuplicateHandle(me, handle_of(2), me, &null_err, 0, 1, 2)) null_err = 0;
    err = null_err;
  }
  }
  /* STARTUPINFOW: cb, ..., dwFlags STARTF_USESTDHANDLES at 60, the
     handles at 80, 88 and 96. */
  u8 startup[104];
  memset(startup, 0, sizeof startup);
  *(u32 *)startup = sizeof startup;
  *(u32 *)(startup + 60) = 0x100;
  *(u64 *)(startup + 80) = in_read;
  *(u64 *)(startup + 88) = out_write;
  *(u64 *)(startup + 96) = err;
  u64 info[3] = {0};                           /* PROCESS_INFORMATION */
  /* CREATE_UNICODE_ENVIRONMENT */
  if (!imp_CreateProcessW(wpath1, line, 0, 0, 1, 0x400, block, directory, startup, info)) { r = fail(); goto close; }
  imp_CloseHandle(info[1]);
  int slot = -1;
  for (int i = 0; i < CHILDREN; i++) if (!child_handle[i]) { slot = i; break; }
  if (slot < 0) {
    imp_CloseHandle(info[0]);
    r = -11;                                   /* EAGAIN: too many */
    goto close;
  }
  child_pid[slot] = (u32)info[2];
  child_handle[slot] = info[0];
  child_timer[slot] = 0;
  if (kill_ms > 0) imp_CreateTimerQueueTimer(&child_timer[slot], 0, end_child, (void *)info[0], (u32)kill_ms, 0, 8);   /* WT_EXECUTEONLYONCE */
  {
    i64 reader = out_read ? new_fd(out_read) : -1;
    out_read = 0;
    i64 writer = -1;
    if (flags & 1) { writer = new_fd(in_write); in_write = 0; }
    i64 *o = (i64 *)out;
    commit_range(o, 16);
    o[0] = reader;
    o[1] = writer;
  }
  r = (i64)(u32)info[2];
close:
  if (out_read) imp_CloseHandle(out_read);
  if (out_write) imp_CloseHandle(out_write);
  if (in_write) imp_CloseHandle(in_write);
  if (in_read) imp_CloseHandle(in_read);
  if (null_err) imp_CloseHandle(null_err);
  return r;
}

/* pipe2(fds, flags): an anonymous pipe, not inherited; 1 MiB of room, so
   that a writer seldom waits on the one thread for a reader. */
static i64 sys_pipe2(i64 fds) {
  u64 r = 0, w = 0;
  if (!imp_CreatePipe(&r, &w, 0, 1 << 20)) return fail();
  i64 a = new_fd(r);
  if (a < 0) { imp_CloseHandle(w); return a; }
  i64 b = new_fd(w);
  if (b < 0) { handles[a] = 0; imp_CloseHandle(r); return b; }
  commit_range((void *)fds, 8);
  ((i32 *)fds)[0] = (i32)a;
  ((i32 *)fds)[1] = (i32)b;
  return 0;
}

/* wait4(pid, status, options): the exit code where Linux puts it in the
   status (code << 8), but the whole 32 bits of it in a word, as Go's
   ExitCode has it there; with WNOHANG, 0 while it runs. */
static i64 sys_wait4(i64 pid, i64 status, i64 options) {
  if (pid == COPY_PID && copy_status >= 0) {
    if (status) {
      commit_range((void *)status, 8);
      *(u64 *)status = (u64)copy_status << 8;
    }
    copy_status = -1;
    return pid;
  }
  int i = child_of(pid);
  if (i < 0) return -10;                       /* ECHILD */
  u32 w = imp_WaitForSingleObject(child_handle[i], (options & 1) ? 0 : 0xFFFFFFFF);
  if (w == 0x102) return 0;                    /* WAIT_TIMEOUT */
  u32 code = 0;
  imp_GetExitCodeProcess(child_handle[i], &code);
  /* The timer goes first, its callback over (INVALID_HANDLE_VALUE): the
     handle is closed below. */
  if (child_timer[i]) { imp_DeleteTimerQueueTimer(0, child_timer[i], (u64)-1); child_timer[i] = 0; }
  if (status) {
    commit_range((void *)status, 8);
    *(u64 *)status = (u64)code << 8;
  }
  imp_CloseHandle(child_handle[i]);
  child_handle[i] = 0;
  return pid;
}

/* kill(pid, signal): SIGKILL ends it as Go's Process.Kill does there
   (TerminateProcess, exit code 1); 0 asks whether it is there; any other
   signal Windows has no way to send. */
static i64 sys_kill(i64 pid, i64 signal) {
  int i = child_of(pid);
  if (i < 0) return -3;                        /* ESRCH */
  if (signal == 0) return 0;
  if (signal != 9) return -EINVAL;
  return imp_TerminateProcess(child_handle[i], 1) ? 0 : fail();
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

/* Go's syscall.Open on Windows refuses an empty path as
   ERROR_FILE_NOT_FOUND (CreateFileW would say the path is not found). */
static int empty_path(i64 p) {
  if (!p) return 0;
  commit_range((void *)p, 1);
  if (*(const char *)p) return 0;
  last_error = 2;
  return 1;
}

/* open for writing of what is a directory: EISDIR, as Go's syscall.Open
   makes of Windows' refusal (with O_EXCL the file exists, as there). */
static i64 open_directory(i64 path, i64 flags) {
  if (!path || !(flags & 3) || (flags & 0xC0) == 0xC0) return NOT_MINE;
  if (!wide((const char *)path, wpath1)) return NOT_MINE;
  u32 a = imp_GetFileAttributesW(wpath1);
  if (a == 0xFFFFFFFF || !(a & 0x10)) return NOT_MINE;
  last_error = 0;
  return -21;                                                /* EISDIR */
}

/* The system call in the CONTEXT at c (its number in RAX): its result, or
   NOT_MINE for the assembly to make. */
i64 layer_call(unsigned char *c) {
  i64 nr = *(i64 *)(c + 0x78);
  last_error = 0;
  if (copying && nr == 1) {
    i64 r = spill_write(ARG(c, 0), ARG(c, 1), ARG(c, 2));
    if (r != NOT_MINE) return r;
  }
  switch (nr) {
  case 57: case 58: return sys_fork(c);                      /* fork, vfork */
  case 60: case 231: return copying ? copy_exit(c, ARG(c, 0)) : NOT_MINE;
  case 3: case 11: case 28:
    /* While a copy runs, closing only leaves the table, and memory is
       neither unmapped nor let go: the parent has it. */
    if (copying) {
      if (nr == 3) { i64 fd = ARG(c, 0); if (fd >= 0 && fd < FDS) { handles[fd] = 0; socket_fd[fd] = 0; } return 0; }
      return 0;
    }
    if (nr == 3) return is_socket(ARG(c, 0)) ? socket_call(nr, c) : NOT_MINE;
    return NOT_MINE;
  case 1000101: return error_text(ARG(c, 0));
  case 1000102: return full_path(ARG(c, 0));
  case 1000103: return temp_dir();
  case 1000105: return local_lookup(ARG(c, 0), ARG(c, 1));
  case 1000107: return sys_resolve(ARG(c, 0), ARG(c, 1), ARG(c, 2));
  case 1000104: return sys_spawn(ARG(c, 0), ARG(c, 1), ARG(c, 2), ARG(c, 3), ARG(c, 4), ARG(c, 5));
  case 61: return sys_wait4(ARG(c, 0), ARG(c, 1), ARG(c, 2));
  case 22: case 293: return sys_pipe2(ARG(c, 0));             /* pipe, pipe2 */
  case 62: return sys_kill(ARG(c, 0), ARG(c, 1));
  case 41: return sys_socket(ARG(c, 0), ARG(c, 1), ARG(c, 2));
  case 271: return sys_ppoll(ARG(c, 0), ARG(c, 1), ARG(c, 2));
  case 0: case 1: case 5: case 16:
    return is_socket(ARG(c, 0)) ? socket_call(nr, c) : NOT_MINE;
  case 72: return is_socket(ARG(c, 0)) ? socket_call(nr, c) : sys_fcntl(ARG(c, 0), ARG(c, 1), ARG(c, 2));
  case 2: return empty_path(ARG(c, 0)) ? -ENOENT : open_directory(ARG(c, 0), ARG(c, 1));  /* open */
  case 32: return sys_dup(ARG(c, 0), 3);
  case 33: case 292: return sys_dup2(ARG(c, 0), ARG(c, 1));
  case 17: return sys_pio(ARG(c, 0), ARG(c, 1), ARG(c, 2), ARG(c, 3), 0);
  case 18: return sys_pio(ARG(c, 0), ARG(c, 1), ARG(c, 2), ARG(c, 3), 1);
  case 9:                                                      /* mmap */
    if (ARG(c, 3) & 0x20 || ARG(c, 4) < 0) return sys_mmap_anonymous(ARG(c, 1), ARG(c, 3));
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
  case 4: case 6: return sys_stat_path(ARG(c, 0), ARG(c, 1), nr == 4);   /* stat, lstat */
  case 262: {                                                  /* newfstatat */
    i64 r = at_call(c, 0);
    if (r != NOT_MINE) return r;
    const char *path = (const char *)ARG(c, 1);
    /* AT_EMPTY_PATH with no path is the descriptor's: the assembly's. */
    if (!path || ((ARG(c, 3) & 0x1000) && !*path)) return NOT_MINE;
    return sys_stat_path((i64)path, ARG(c, 2), !(ARG(c, 3) & 0x100));   /* AT_SYMLINK_NOFOLLOW */
  }
  case 280: {                                                  /* utimensat */
    i64 r = at_call(c, 0);
    if (r != NOT_MINE) return r;
    return ARG(c, 1) ? sys_utimens(ARG(c, 1), ARG(c, 2)) : -EINVAL;
  }
  /* copy_file_range: not here; the library reads and writes instead. */
  case 326: return -ENOSYS;
  case 87: return sys_unlink(ARG(c, 0));
  case 89: return sys_readlink(ARG(c, 0), ARG(c, 1), ARG(c, 2));
  case 267: {                                                  /* readlinkat */
    i64 r = at_call(c, 0);
    if (r != NOT_MINE) return r;
    return ARG(c, 1) ? sys_readlink(ARG(c, 1), ARG(c, 2), ARG(c, 3)) : -EINVAL;
  }
  case 263: {                                                  /* unlinkat */
    i64 r = at_call(c, 0);
    if (r != NOT_MINE || (ARG(c, 2) & 0x200) || !ARG(c, 1)) return r;   /* AT_REMOVEDIR: the assembly's */
    return sys_unlink(ARG(c, 1));
  }
  case 257: {                                                  /* openat */
    if (empty_path(ARG(c, 1))) return -ENOENT;
    i64 r = at_call(c, 0);
    return r != NOT_MINE ? r : open_directory(ARG(c, 1), ARG(c, 2));
  }
  case 258: return at_call(c, 0);                              /* mkdirat */
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
