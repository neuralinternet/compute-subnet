import hashlib

import torch


# Convertir une chaîne en tensor
def string_to_tensor(string):
    return torch.tensor(bytearray(string.encode()), dtype=torch.uint8, device="cuda")


# Calculer le hachage SHA256 à l'aide de hashlib
def calculate_sha256_hash(data, difficulty=4):
    nonce = 0
    while True:
        hashed_data = hashlib.sha256(data).hexdigest()

        if hashed_data.startswith("0" * difficulty):
            return nonce, hashed_data

        nonce += 1

        block_content = f"{hashed_data} - {nonce}"
        print(block_content)

    return hashed_data


def proof_of_work(subtensor, wallet, netuid=27):
    question = "generated question"

    data_tensor = string_to_tensor(question)

    # Convertir le tensor en bytes et calculer le hachage SHA256
    hashed_data = calculate_sha256_hash(data_tensor.cpu().numpy().tobytes())

    print(f"Hash SHA256 calculé avec Python : {hashed_data}")


if __name__ == "__main__":
    proof_of_work()
