#define _POSIX_C_SOURCE 200809L
#include <setjmp.h>
#include <signal.h>
#include <stdio.h>

int main(void)
{
    sigjmp_buf env;
    sigset_t mask, previous, current;

    if (sigsetjmp(env, 0) == 0)
        siglongjmp(env, 1);

    if (sigemptyset(&mask) || sigaddset(&mask, SIGUSR1)
        || sigprocmask(SIG_BLOCK, &mask, &previous))
        return 1;

    if (sigsetjmp(env, 1) == 0) {
        if (sigprocmask(SIG_UNBLOCK, &mask, NULL))
            return 2;
        siglongjmp(env, 2);
    }

    if (sigprocmask(SIG_SETMASK, NULL, &current)
        || sigismember(&current, SIGUSR1) != 1)
        return 3;

    if (sigprocmask(SIG_SETMASK, &previous, NULL))
        return 4;

    puts("AArch64 musl sigsetjmp/longjmp checks passed.");
    return 0;
}
