import time

import numpy as np
import pycuda
import pycuda.driver as cuda
from pycuda._driver import Context
from pycuda.compiler import SourceModule


def proof_of_work_cuda(question, difficulty):
    cuda.init()
    device = cuda.Device(0)  # enter your gpu id here
    ctx = device.make_context()

    block_size = 256  # Taille du bloc CUDA
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

    Context.pop()
    return nonce_found, valid_answer, end_time - start_time


# Exemple d'utilisation
question_from_validator = "Quelle est la couleur du ciel ?"
difficulty_level = 4  # Difficulté : nombre de zéros requis au début de la réponse

nonce_found, valid_answer, time_taken = proof_of_work_cuda(question_from_validator, difficulty_level)
if nonce_found is not None:
    print(f"Nonce trouvé : {nonce_found}")
    print(f"Réponse valide : {valid_answer}")
    print(f"Temps pris : {time_taken} secondes")
else:
    print("Impossible de trouver une réponse dans les 120 secondes.")

pycuda.driver.Context.pop()
