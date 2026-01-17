from time import time
import hashlib
import json
from uuid import uuid4
from textwrap import dedent
from flask import Flask,jsonify, request
from flask_cors import CORS
from urllib.parse import urlparse
import requests
from pathlib import Path

class Blockchain(object):
    def __init__(self, data_dir='data'):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.chain_file = self.data_dir / 'blockchain.json'
        
        self.chain = []
        self.current_transactions = []
        self.nodes = set()
        
        # Load existing blockchain or create new one
        if self.chain_file.exists():
            self.load_chain()
        else:
            self.new_block(proof=100, previous_hash='0')
            self.save_chain()
        
    def new_block(self, proof, previous_hash = None):
        """
        Create a new Block in the Blockchain
        :param proof: <int> The proof given by the Proof of Work algorithm
        :param previous_hash: (Optional) <str> Hash of the previous Block
        :return: <dict> New Block
        """
        
        block = {
            'index': len(self.chain) + 1,
            'timestamp' : time(),
            'transactions' : self.current_transactions,
            'proof' : proof,
            'previous_hash' : previous_hash or self.hash(self.chain[-1]),
            }
        
        # Reset the current list of transactions
        self.current_transactions = []

        self.chain.append(block)
        self.save_chain()  # Save after adding new block
        return block
    
    def new_transaction(self, sender, recipient, amount):
        """
        Creates a new transaction to go into the next mined Block
        :param sender: <str> Address of the Sender
        :param recipient: <str> Address of the Recipient
        :param amount: <int> Amount
        :return: <int> The index of the Block that will hold this transaction
        """

        self.current_transactions.append({
            'sender' : sender,
            'recipient' : recipient,
            'amount' : amount,
        })

        return self.last_block['index'] + 1
    
    @staticmethod
    def hash(block):
        """
        Creates a SHA-256 hash of a Block
        :param block: <dict> Block
        :return: <str>
        """

        # We must make sure that the Dictionary is Ordered, or we'll have insconsistent hashes
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]
    
    def proof_of_work(self,last_proof):
        """
        Simple proof of Work Algorithm:
        - Find a number p' such that hash(pp') contains leading 4 zeroes, where p is the previous p'
        - p is the previous proof, and p' is the new proof
        :param last_proof: <int>
        :return: <int>
        """

        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof +=1

        return proof
    
    @staticmethod
    def valid_proof(last_proof, proof):
        """
        Validates the Proof: Does hash(last_proof, proof) contains 4 leading zeros?
        :param last_proof: <int> Previous Proof
        :param proof: <int> Current Proof
        :return: <bool> True if correct, False if not.
        """

        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"
    
    def register_node(self, address):
        """
        Add a new node to the list of nodes
        :param address: <str> Address of node. Eg. 'http://192.168.0.1:5000'
        :return: None
        """

        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def valid_chain(self, chain):
        """
        Determine if a given blockchain is valid
        :param self: <list> A blockchain
        :param chain: <bool> True if valid, False if not
        """

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f"{last_block}")
            print(f"{block}")
            print("\n-----------\n")
            # Check that the hash of the block is correct
            if block['previous_hash'] != self.hash(last_block):
                return False
            
            # Check that the Proof of Work is correct
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False
            
            last_block = block
            current_index +=1


        return True
    
    def resolve_conflicts(self):
        """
        This is our Consensus Algorithm, it resolves conflicts by replacing our chain with the longest one in the network
        :return: <bool> True if our chain was replaced, False if not
        """

        neighbours = self.nodes
        new_chain = None

        # We're only looking for chains longer than ours
        max_length = len(self.chain)

        # Grab and verify the chains from all the nodes in our network
        for node in neighbours:
            response = requests.get(f"http://{node}/chain")

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # Check if the length is longer and the chain is valid
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # Replace our chain if we discovered a new, valid chain longer than ours
        if new_chain:
            self.chain = new_chain
            return True
        
        return False
    
    def get_balance(self, address):
        balance = 0
        for block in self.chain:
            for tx in block['transactions']:
                if tx['recipient'] == address:
                    balance += tx['amount']
                if tx['sender'] == address:
                    balance -= tx['amount']
        
        for tx in self.current_transactions:
            if tx['recipient'] == address:
                balance += tx['amount']
            if tx['sender'] == address:
                balance -= tx['amount']
        
        return balance
    
    def save_chain(self):
        """Save blockchain to disk"""
        data = {
            'chain': self.chain,
            'current_transactions': self.current_transactions
        }
        with open(self.chain_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_chain(self):
        """Load blockchain from disk"""
        try:
            with open(self.chain_file, 'r') as f:
                data = json.load(f)
                self.chain = data.get('chain', [])
                self.current_transactions = data.get('current_transactions', [])
        except (json.JSONDecodeError, FileNotFoundError):
            # If file is corrupted or doesn't exist, initialize fresh chain
            self.chain = []
            self.current_transactions = []

        
    
app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Generate a unique address for this node
node_identifier = str(uuid4()).replace('-','')

blockchain = Blockchain()

@app.route('/', methods=['GET'])
def index():
    return app.send_static_file('index.html')

@app.route('/api/home', methods=['GET'])
def home():
    return jsonify({'message': 'Welcome to PyChain'}), 200

@app.route('/mine', methods=['GET'])
def mine():
    # We run the proof of wwork algotritm to get the next proof
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    # We must recieve a reward for finding the proof.
    # The sender is "0" to signify that ths node has mined a new coin.
    blockchain.new_transaction(
        sender="0",
        recipient=node_identifier,
        amount=1,
    )

    # Forge the new Block by adding it to the chain
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)

    response = {
        'message' : "New Block Forged" , 
        'index' : block['index'],
        'transactions' : block['transactions'],
        'proof' : block['proof'],
        'previous_hash' : block['previous_hash'],
    }

    return jsonify(response), 200

@app.route('/transactions/new', methods=['POST'])
def new_transactions():
    values = request.get_json()

    # Check that the requried fields are in the POST'ed data
    required = ['sender', 'recipient', 'amount']
    if not values or not all(k in values for k in required):
        return 'Missing values', 400

    # Create a new Transaction
    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

    response = {'message': f'Transaction wil be added to Block{index}'}
    return jsonify(response), 201

@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain)
        }
    return jsonify(response), 200

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes" , 400
    
    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'new_chain': blockchain.chain
        }
    return jsonify(response), 200

@app.route('/balance/<address>', methods=['GET'])
def get_balance(address):
    balance = blockchain.get_balance(address)
    return jsonify({
        'address':address,
        'balance':balance
    }), 200

FAUCET_AMOUNT = 100
faucet_requests = {}

@app.route('/faucet', methods=['POST'])
def faucet():
    values = request.get_json()
    address = values.get('address')

    if not address:
        return jsonify({'error': 'Address required'}), 400
    
    # Prevent spamming faucet
    if address in faucet_requests:
        import time as time_module
        if time_module.time() - faucet_requests[address] < 60:
            return jsonify({'error': 'Faucet cooldown. Try again in 1 minute.'}), 429
    
    blockchain.new_transaction(
        sender="0",
        recipient=address,
        amount=FAUCET_AMOUNT
    )
    
    faucet_requests[address] = time()

    return jsonify({
        'message': f'{FAUCET_AMOUNT} coins sent to {address}',
        'success': True,
        'amount': FAUCET_AMOUNT
    }), 200

BURN_ADDRESS = "POST_FEE"
BASE_POST_COST = 10

# Data persistence
DATA_DIR = Path('data')
DATA_DIR.mkdir(exist_ok=True)
POSTS_FILE = DATA_DIR / 'posts.json'
USERS_FILE = DATA_DIR / 'users.json'

def load_posts():
    """Load posts from disk"""
    if POSTS_FILE.exists():
        try:
            with open(POSTS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            return []
    return []

def save_posts(posts_data):
    """Save posts to disk"""
    with open(POSTS_FILE, 'w') as f:
        json.dump(posts_data, f, indent=2)

def load_users():
    """Load registered users from disk"""
    if USERS_FILE.exists():
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}

def save_users(users_data):
    """Save registered users to disk"""
    with open(USERS_FILE, 'w') as f:
        json.dump(users_data, f, indent=2)

def generate_unique_address():
    """Generate guaranteed unique address"""
    users = load_users()
    timestamp = str(int(time() * 1000))  # millisecond timestamp
    random_part = str(uuid4())[:8]
    address = f"addr_{timestamp}_{random_part}"
    
    # Save to users registry
    users[address] = {
        'created_at': time(),
        'last_seen': time()
    }
    save_users(users)
    
    return address

@app.route('/generate-address', methods=['POST'])
def generate_address_endpoint():
    """Generate a unique blockchain address - one per device"""
    values = request.get_json()
    device_id = values.get('device_id')
    
    if not device_id:
        return jsonify({'error': 'Device ID required'}), 400
    
    users = load_users()
    
    # Check if this device already has an address
    for address, info in users.items():
        if info.get('device_id') == device_id:
            # Device already registered, return existing address
            return jsonify({
                'address': address,
                'success': True,
                'existing': True,
                'message': 'Welcome back! Using your existing address.'
            }), 200
    
    # Generate new address for new device
    timestamp = str(int(time() * 1000))
    random_part = str(uuid4())[:8]
    address = f"addr_{timestamp}_{random_part}"
    
    # Save with device ID
    users[address] = {
        'created_at': time(),
        'last_seen': time(),
        'device_id': device_id
    }
    save_users(users)
    
    return jsonify({
        'address': address,
        'success': True,
        'existing': False,
        'message': 'New wallet created!'
    }), 200

posts = load_posts()

def calculate_post_cost():
    """Dynamic cost increases with number of posts"""
    return BASE_POST_COST + (len(posts) // 5)

@app.route('/post', methods=['POST'])
def create_post():
    values = request.get_json()
    address = values.get('address')
    content = values.get('content')
    cost = calculate_post_cost()

    if not address or not content:
        return jsonify({'error': 'Address and content required'}), 400
    
    balance = blockchain.get_balance(address)
    if balance < cost:
        return jsonify({
            'error': 'Insufficient balance',
            'needed': cost,
            'balance': balance
        }), 403
    
    # Charge user
    blockchain.new_transaction(
        sender=address,
        recipient=BURN_ADDRESS,
        amount=cost
    )

    # Create post with unique ID
    post_data = {
        'id': str(uuid4()),
        'address': address,
        'content': content,
        'timestamp': time(),
        'cost': cost
    }
    posts.append(post_data)
    save_posts(posts)  # Save to disk

    return jsonify({
        'message': 'post created',
        'success': True,
        'cost': cost,
        'new_balance': blockchain.get_balance(address)
    }), 201

@app.route('/posts', methods=['GET'])
def get_posts():
    return jsonify({
        'posts': posts,
        'total': len(posts),
        'next_post_cost': calculate_post_cost()
    }), 200

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)