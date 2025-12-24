import time
import random

class SystemMonitor:
    def __init__(self):
        # Initial Metaphorical States based on user prompt
        self.equity = 94.2
        self.prosperity = 98.7
        self.last_tick = time.time()
        self.status_log = []

    def tick(self):
        """Simulate dynamic changes in system state"""
        now = time.time()
        if now - self.last_tick > 5: # update every 5s
            self.last_tick = now
            
            # Semantic Drift Simulation
            # Equity fluctuates based on "balance"
            self.equity += random.uniform(-0.5, 0.5)
            self.equity = max(0, min(100, self.equity))
            
            # Prosperity grows slightly but can dip
            self.prosperity += random.uniform(-0.2, 0.3)
            self.prosperity = max(0, min(100, self.prosperity))
            
            # Self-Optimization Triggers
            if self.equity < 90:
                self._optimize("Equity")
            if self.prosperity < 95:
                self._optimize("Prosperity")

    def _optimize(self, metric):
        """Metaphorical self-healing"""
        msg = f"[AUTO-FIX] {metric} dropped. Re-aligning vectors..."
        self.status_log.append(msg)
        # Boost back up
        if metric == "Equity": self.equity += 2.0
        if metric == "Prosperity": self.prosperity += 1.5
        
        # Keep log clean
        if len(self.status_log) > 5: self.status_log.pop(0)

    def get_status_str(self):
        return f"Equity: {self.equity:.1f}% | Prosperity: {self.prosperity:.1f}%"
