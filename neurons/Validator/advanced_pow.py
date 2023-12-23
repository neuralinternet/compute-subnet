# The method contained within this file are for now testing purpose.
# It is not integrated yet to the code.
# This is an improvement to start working on once the general algorithm is validated.
# This part will ensure that the GPUs are necessarily used instead of CPUs and optimize essentially the
# Hash rates from GPUs as it is the mindset of the subnet-27

import time

import numpy as np
import pycuda
import pycuda.driver as cuda
from pycuda.compiler import SourceModule

from compute import pow_min_difficulty
from neurons.Validator.basic_pow import generate_random_header


def proof_of_work_cuda(question, difficulty):
    cuda.init()
    device = cuda.Device(0)
    ctx = device.make_context()

    block_size = 256
    question_bytes = question.encode("utf-8")
    question_gpu = cuda.mem_alloc(len(question_bytes))
    cuda.memcpy_htod(question_gpu, question_bytes)

    mod = SourceModule(
        """
    __global__ void sha256_kernel(char *question, int *nonce, char *result, int difficulty)
    {
        unsigned int idx = threadIdx.x + blockIdx.x * blockDim.x;
        char data[256];
        char answer[64];
        int i;

        while(1) {
            data[idx] = question[idx];
            data[256 - 1] = nonce[0] & 0xFF;
            data[256 - 2] = (nonce[0] >> 8) & 0xFF;
            data[256 - 3] = (nonce[0] >> 16) & 0xFF;
            data[256 - 4] = (nonce[0] >> 24) & 0xFF;

            sha256(data, 256, answer);

            int valid = 1;
            for(i = 0; i < difficulty; i++) {
                if(answer[i] != 0) {
                    valid = 0;
                    break;
                }
            }

            if(valid) {
                for(i = 0; i < 32; i++) {
                    result[i] = answer[i];
                }
                break;
            }

            nonce[0]++;
        }
    }
    """
    )

    sha256 = mod.get_function("sha256_kernel")

    nonce = np.array([0], dtype=np.int32)
    result = np.zeros(32, dtype=np.uint8)
    difficulty = np.array([difficulty], dtype=np.int32)

    start_time = time.time()
    sha256(question_gpu, cuda.InOut(nonce), cuda.Out(result), cuda.In(difficulty), block=(block_size, 1, 1))
    end_time = time.time()

    valid_answer = bytes(result)
    nonce_found = nonce[0]

    pycuda.driver.Context.pop()
    return nonce_found, valid_answer, end_time - start_time


nonce_found, valid_answer, time_taken = proof_of_work_cuda(generate_random_header(), pow_min_difficulty)
