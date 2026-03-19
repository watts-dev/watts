from mpi4py import MPI
from watts.fileutils import cd_tmpdir
import os
# checking to make sure each tmpdir only created with rank 0
# to run test run standalone script with 
# mpiexec -np 2 python test_mpi_tmpdir.py

green = '\033[92m'
red =  '\033[91m'
reset = '\033[0m'
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

with cd_tmpdir():
    tmpdir = os.getcwd()

    # Gather all ranks' directories to rank 0
    all_dirs = comm.gather(tmpdir, root=0)

    if rank == 0:
        print(f"\nRunning MPI tmp directory test with {size} ranks")
        print(f"{'─' * 50}")
        for i, d in enumerate(all_dirs):
            print(f"  Rank {i}: {d}")
        print(f"{'─' * 50}")

        # Check all directories are the same
        unique_dirs = set(all_dirs)
        if len(unique_dirs) == 1:
            print(f"{green}PASSED: All {size} ranks share the same tmp directory{reset}\n")
        else:
            print(f"{red}FAILED: Ranks have different tmp directories!{reset}")
            print(f"{red}Expected 1 unique directory, got {len(unique_dirs)}{reset}\n")
            raise AssertionError("MPI ranks do not share the same tmp directory")

# verify cleanup of tmpdir 
if rank == 0:
    if not os.path.exists(tmpdir):
        print(f"{green}PASSED: Tmp directory was cleaned up correctly{reset}\n")
    else:
        print(f"{red}FAILED: Tmp directory was not cleaned up{reset}\n")
        raise AssertionError("Tmp directory was not cleaned up after context manager exit")