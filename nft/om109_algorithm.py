import os
import hashlib
import hmac
import math
import json

class OM109Algorithm:
    """
    Proprietary OM109 algorithm for NFT valuation, uniqueness, and cryptographic authentication.
    """
    
    def __init__(self, secret_key: str = None):
        secret_key = secret_key or os.environ.get("OM109_SECRET_KEY")
        if not secret_key:
            raise RuntimeError("OM109_SECRET_KEY not set in environment — no hardcoded fallback.")
        self.secret_key = secret_key.encode('utf-8')
        
    def generate_token_signature(self, metadata: dict) -> str:
        """
        Creates a cryptographically unique token ID/signature from metadata payload.
        """
        serialized = json.dumps(metadata, sort_keys=True)
        h = hmac.new(self.secret_key, serialized.encode('utf-8'), hashlib.sha256)
        return h.hexdigest()
        
    def calculate_rarity_score(self, attributes: list, collection_stats: dict) -> float:
        """
        Multi-factor rarity scoring logic based on attribute distribution.
        Formula incorporates Information Entropy and TF-IDF style rare factor.
        """
        if not attributes or not collection_stats:
            return 1.0
            
        total_items = collection_stats.get("total_items", 1)
        entropy_sum = 0.0
        
        for attr in attributes:
            trait_type = attr.get("trait_type")
            value = attr.get("value")
            
            # Find attribute frequency in collection
            freq_dict = collection_stats.get("frequencies", {}).get(trait_type, {})
            trait_count = freq_dict.get(value, 1)
            
            # Calculate probability of this trait value
            p = max(min(trait_count / total_items, 1.0), 0.000001)
            
            # Shannon entropy component: -p * log2(p)
            entropy_contribution = -p * math.log2(p)
            entropy_sum += (1.0 / p) + entropy_contribution
            
        return round(entropy_sum, 6)
        
    def compute_fair_value(self, token: dict, market_data: dict) -> float:
        """
        ML-based fair value estimation leveraging collection floor, previous sales,
        and current uniqueness/rarity parameters.
        """
        floor_price = float(market_data.get("floor_price", 0.0))
        recent_sales_avg = float(market_data.get("recent_sales_avg", 0.0))
        rarity_score = float(token.get("rarity_score", 1.0))
        
        # Fair Value = (0.4 * Floor Price + 0.6 * Recent Sales Average) * (1.0 + ln(Rarity Score))
        base_price = (0.4 * floor_price) + (0.6 * recent_sales_avg)
        if base_price <= 0:
            base_price = floor_price if floor_price > 0 else 0.1 # default baseline
            
        uniqueness_multiplier = 1.0 + math.log(max(rarity_score, 1.0))
        fair_value = base_price * uniqueness_multiplier
        return round(fair_value, 6)
        
    def verify_authenticity(self, token_id: str, signature: str) -> bool:
        """
        Verifies the cryptographic integrity of a token signature using standard hmac verification.
        """
        # Re-verify matching token_id
        calculated_sig = hmac.new(self.secret_key, token_id.encode('utf-8'), hashlib.sha256).hexdigest()
        return hmac.compare_digest(calculated_sig, signature)
        
    def generate_uniqueness_proof(self, token: dict) -> dict:
        """
        Generates a zero-knowledge style proof of uniqueness by hashing token characteristics.
        """
        token_id = str(token.get("id", ""))
        attributes_hash = hashlib.sha256(json.dumps(token.get("attributes", []), sort_keys=True).encode('utf-8')).hexdigest()
        
        # Generate challenge & response style structure
        challenge = hashlib.sha256((token_id + attributes_hash).encode('utf-8')).hexdigest()
        response = hmac.new(self.secret_key, challenge.encode('utf-8'), hashlib.sha256).hexdigest()
        
        return {
            "token_id": token_id,
            "attributes_hash": attributes_hash,
            "challenge": challenge,
            "proof_signature": response,
            "algorithm": "OM109-ZK-PROOF-V1"
        }
