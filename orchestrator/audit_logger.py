import sqlite3
import json
from datetime import datetime
from typing import Any, Dict, Optional

class AuditLogger:
    def __init__(self, db_path: str = "audit_log.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    input_data TEXT,
                    output_data TEXT,
                    confidence REAL,
                    metadata TEXT
                )
            """)

    def log(self, agent_name: str, action: str, input_data: Any, 
            output_data: Any, confidence: Optional[float] = None, 
            metadata: Optional[Dict[str, Any]] = None):
        
        timestamp = datetime.utcnow().isoformat()
        
        # Serialize complex data
        input_str = json.dumps(input_data) if input_data else None
        output_str = json.dumps(output_data) if output_data else None
        metadata_str = json.dumps(metadata) if metadata else None

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO audit_logs 
                (timestamp, agent_name, action, input_data, output_data, confidence, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (timestamp, agent_name, action, input_str, output_str, confidence, metadata_str))

    def get_logs(self, agent_name: Optional[str] = None):
        query = "SELECT * FROM audit_logs"
        params = []
        if agent_name:
            query += " WHERE agent_name = ?"
            params.append(agent_name)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
