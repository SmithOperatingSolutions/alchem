/* Benchmark helper only: report one child's peak RSS in KiB on Linux.
 * This is not part of either compiler or the IR compilation path. */
#define _DEFAULT_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    pid_t pid = fork();
    if (pid < 0) { perror("fork"); return 1; }
    if (pid == 0) {
        execv(argv[1], argv + 1);
        perror("execv");
        _exit(127);
    }
    int status;
    struct rusage usage;
    if (wait4(pid, &status, 0, &usage) < 0) { perror("wait4"); return 1; }
    if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) return 1;
    printf("%ld\n", usage.ru_maxrss);
    return 0;
}
