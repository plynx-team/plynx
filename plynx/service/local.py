import subprocess


def run_local(num_workers, verbose):
    assert num_workers > 0, 'There must be one or more Workers'

    verbose_flags = ['-v'] * verbose

    processes = [
        ['plynx', 'backend'] + verbose_flags,
        ['plynx', 'master'] + verbose_flags,
    ]
    processes.extend([['plynx', 'worker'] + verbose_flags] * num_workers)

    procs = [subprocess.Popen(process) for process in processes]
    for p in procs:
        p.wait()
