class TransactionCost:
    def __init__(self, commission: float = 0.0, slippage_pct: float = 0.001):
        self.commission = commission
        self.slippage_pct = slippage_pct
    
    def calculate_entry_cost(self, shares: float, price: float) -> float:
        if shares <= 0:
            raise ValueError(f"Shares must be positive, got {shares}")
        if price <= 0:
            raise ValueError(f"Price must be positive, got {price}")
        
        base_cost = shares * price
        slippage_cost = base_cost * self.slippage_pct
        total = base_cost + slippage_cost + self.commission
        return total
    
    def calculate_exit_value(self, shares: float, price: float) -> float:
        if shares <= 0:
            raise ValueError(f"Shares must be positive, got {shares}")
        if price <= 0:
            raise ValueError(f"Price must be positive, got {price}")
        
        gross_proceeds = shares * price
        slippage_cost = gross_proceeds * self.slippage_pct
        net_proceeds = gross_proceeds - slippage_cost - self.commission
        
        return net_proceeds