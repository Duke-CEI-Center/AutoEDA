#!/usr/bin/env python3
"""
EDA Server Launcher

This script launches any of the four EDA servers:
- Synthesis server
- Placement server  
- CTS server
- Routing server

Usage:
    python run_server.py --server synthesis
    python run_server.py --server placement
    python run_server.py --server cts
    python run_server.py --server routing
    python run_server.py --server all

API Usage:
curl -X POST http://localhost:13333/run -H "Content-Type: application/json" -d '{"design": "des", "tech": "FreePDK45"}' | python -m json.tool
curl -X POST http://localhost:13340/run -H "Content-Type: application/json" -d '{"design": "des", "tech": "FreePDK45"}' | python -m json.tool
curl -X POST http://localhost:13341/run -H "Content-Type: application/json" -d '{"design": "des", "tech": "FreePDK45"}' | python -m json.tool
curl -X POST http://localhost:13342/run -H "Content-Type: application/json" -d '{"design": "des", "tech": "FreePDK45"}' | python -m json.tool

curl -X POST http://localhost:15333/run -H "Content-Type: application/json" -d '{"design": "des", "tech": "FreePDK45"}' | python -m json.tool
curl -X POST http://localhost:15334/run -H "Content-Type: application/json" -d '{"design": "des", "tech": "FreePDK45"}' | python -m json.tool
curl -X POST http://localhost:15335/run -H "Content-Type: application/json" -d '{"design": "des", "tech": "FreePDK45"}' | python -m json.tool
curl -X POST http://localhost:15336/run -H "Content-Type: application/json" -d '{"design": "des", "tech": "FreePDK45"}' | python -m json.tool
"""

import argparse
import sys
import threading
import time
import signal
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# Add unified_server to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent / "unified_server"))

def main():
    parser = argparse.ArgumentParser(
        description="EDA Server Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run_server.py --server synthesis --port 13333

API Usage:
curl -X POST http://localhost:13333/run -H "Content-Type: application/json" -d '{"design": "des", "tech": "FreePDK45"}'
        """
    )
    parser.add_argument(
        "--server",
        type=str,
        choices=["synthesis", "placement", "cts", "routing", "all"],
        required=True,
        help="Server type to run"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Listen port (overrides environment variable and default)",
    )
    args = parser.parse_args()

    # Import and run the appropriate server
    if args.server == "synthesis":
        from synthesis_server import UnifiedSynthServer
        server = UnifiedSynthServer()
    elif args.server == "placement":
        from placement_server import UnifiedPlacementServer
        server = UnifiedPlacementServer()
    elif args.server == "cts":
        from cts_server import UnifiedCtsServer
        server = UnifiedCtsServer()
    elif args.server == "routing":
        from routing_server import UnifiedRoutingServer
        server = UnifiedRoutingServer()
    elif args.server == "all":
        from synthesis_server import UnifiedSynthServer
        server1 = UnifiedSynthServer()
        from placement_server import UnifiedPlacementServer
        server2 = UnifiedPlacementServer()
        from cts_server import UnifiedCtsServer
        server3 = UnifiedCtsServer()
        from routing_server import UnifiedRoutingServer
        server4 = UnifiedRoutingServer()
    else:
        print(f"Unknown server type: {args.server}")
        sys.exit(1)
    
    if args.server == "all":        
        # Start each server on its default port
        def run_server_in_thread(server, port):
            try:
                server.run_server(port)
            except Exception as e:
                print(f"Error starting server on port {port}: {e}")
        
        port_synth = int(os.getenv("UNIFIED_SYNTHESIS_PORT", 13333))
        port_placement = int(os.getenv("UNIFIED_PLACEMENT_PORT", 13340))
        port_cts = int(os.getenv("UNIFIED_CTS_PORT", 13341))
        port_routing = int(os.getenv("UNIFIED_ROUTING_PORT", 13342))

        print(f"Starting all servers on their configured ports...")
        print(f"Synthesis server: port {port_synth}")
        print(f"Placement server: port {port_placement}")
        print(f"CTS server: port {port_cts}")
        print(f"Routing server: port {port_routing}")

        # Start servers in separate threads (daemon=True so they exit when main thread exits)
        t1 = threading.Thread(target=run_server_in_thread, args=(server1, port_synth), daemon=True)
        t2 = threading.Thread(target=run_server_in_thread, args=(server2, port_placement), daemon=True)
        t3 = threading.Thread(target=run_server_in_thread, args=(server3, port_cts), daemon=True)
        t4 = threading.Thread(target=run_server_in_thread, args=(server4, port_routing), daemon=True)
        
        t1.start()
        t2.start()
        t3.start()
        t4.start()
        
        print("All servers started. Press Ctrl+C to stop all servers.")
        
        try:
            # Keep main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping all servers...")
            print("All servers stopped.")
            sys.exit(0)
    else:
        print(f"Starting {args.server} server...")
        server.run_server(args.port)

if __name__ == "__main__":
    main() 