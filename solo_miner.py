import json
from web3 import Web3
import sha3
import codecs
from random import getrandbits
import time

SETTINGS_LOAD = open('settings.json').read()
SETTINGS = json.loads(SETTINGS_LOAD)[0]
ABI = open('abi.json').read()
client = Web3(Web3.HTTPProvider(SETTINGS['RPC_URL']))
contract = client.eth.contract(address=SETTINGS['CONTRACT_ADDRESS'], abi=ABI)
hash_rate = 0


def generate_nonce():
    myhex = b'%064x' % getrandbits(32 * 8)
    return codecs.decode(myhex, 'hex_codec')


def mine(challenge, public_key, difficulty, epoch):
    # calculate the amount of times we run the loop per minute
    loops = 0
    start_time = time.time()
    last_time = time.time()
    while True:
        loops += 1
        nonce = generate_nonce()
        hash1 = int(sha3.keccak_256(challenge + public_key + nonce).hexdigest(), 16)

        if hash1 < difficulty:
            #find lastest difficulty period length
            #get current block number
            block_number = client.eth.blockNumber
            #get difficulty period length
            difficulty_period_length = block_number - contract.functions.latestDifficultyPeriodStarted().call()
            print("OP blocks passed since last difficulty adjustment:", difficulty_period_length)

            final_hash = sha3.keccak_256(challenge + public_key + nonce).hexdigest()
            # convert nonce from bytes to hex
            nonce = int.from_bytes(nonce, "big")
            return nonce, hash1, final_hash
        else:
            if last_time < (time.time() - 1):
                last_time = time.time()
                hash_rate = loops / 1000000
                print("Mining: " + str(hash_rate) + "Kh/s")
                loops = 0


        #check to make sure we are still on same epoch
        if start_time < (time.time() - 5):
            if epoch != contract.functions.epochCount().call():
                print("New epoch detected! Mining again...")
                final_hash = sha3.keccak_256(challenge + public_key + nonce).hexdigest()
                return nonce, hash1, final_hash
            else:
                start_time = time.time()

def wait_for_receipt(tx_hash):
    tx_receipt = client.eth.getTransactionReceipt(tx_hash)
    while tx_receipt is None:
        tx_receipt = client.eth.getTransactionReceipt(tx_hash)
        print("Waiting for transaction to be mined...")
        time.sleep(1)
    print("Transaction mined!")


def mine_block(valid_nonce, final_hash):
    tx = contract.functions.mine(valid_nonce, final_hash).buildTransaction({
        'gasPrice': client.eth.gasPrice,
        'gas': 350000,
        'from': Web3.toChecksumAddress(SETTINGS['WALLET_ADDRESS']),
        'nonce': client.eth.getTransactionCount(SETTINGS['WALLET_ADDRESS'])
    })
    signed_tx = client.eth.account.signTransaction(tx, private_key=SETTINGS['PRIVATE_KEY'])
    tx_hash = client.eth.sendRawTransaction(signed_tx.rawTransaction)
    # print("Transaction Hash: ", tx_hash.hex())
    return tx_hash



def main():
    print('Mining Active!')
    challenge_hex = contract.functions.getChallengeNumber().call().hex()
    challenge = codecs.decode(challenge_hex, 'hex_codec')
    public_key_hex = SETTINGS['WALLET_ADDRESS'].replace('0x', '')
    public_key = codecs.decode(public_key_hex, 'hex_codec')
    difficulty = contract.functions.miningTarget().call()
    mine_difficulty = contract.functions.getMiningDifficulty().call()
    epoch = contract.functions.epochCount().call()
    print("Difficulty Rate:", mine_difficulty)
    valid_nonce, resulting_hash, final_hash = mine(challenge, public_key, difficulty, epoch)

    if resulting_hash < difficulty:
        print('Solved Block Challenge!')
        # append 0x to final hash + additional 0's to make it 32 bytes
        final_hash = '0x' + final_hash + '0' * (64 - len(final_hash))
        print("Block Found Sending Proof to Contract... Please wait for block to be mined.")
        try:
            tx_hash = mine_block(valid_nonce, final_hash)
            # check if transaction was mined
            try:
                time.sleep(7)
                wait_for_receipt(tx_hash)
            except Exception as e:
                # keep trying until it is mined
                time.sleep(7)
                wait_for_receipt(tx_hash)
        except ValueError as e:
            print("Error:", e)

    else:
        print('Failed to solve block challenge!')

if __name__ == "__main__":

    while True:
        main()
