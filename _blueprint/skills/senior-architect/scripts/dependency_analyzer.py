#!/usr/bin/env python3
"""
Dependency Analyzer
Automated tool for senior architect tasks
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional

class DependencyAnalyzer:
    """Main class for dependency analyzer functionality"""
    
    def __init__(self, target_path: str, verbose: bool = False):
        self.target_path = Path(target_path)
        self.verbose = verbose
        self.results = {}
    
    def run(self) -> Dict:
        """Execute the main functionality"""
        print(f"🚀 Running {self.__class__.__name__}...")
        print(f"📁 Target: {self.target_path}")
        
        try:
            self.validate_target()
            self.analyze()
            self.generate_report()
            
            print("✅ Completed successfully!")
            return self.results
            
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)
    
    def validate_target(self):
        """Validate the target path exists and is accessible"""
        if not self.target_path.exists():
            raise ValueError(f"Target path does not exist: {self.target_path}")
        
        if self.verbose:
            print(f"✓ Target validated: {self.target_path}")
    
    def analyze(self):
        """Scan markdown files for dependency links in YAML front-matter"""
        if self.verbose:
            print("📊 Scanning artifacts for dependencies...")
        
        self.results['status'] = 'success'
        self.results['target'] = str(self.target_path)
        self.results['graph'] = {}
        
        # Walk through _blueprint directory
        for root, dirs, files in os.walk(self.target_path):
            for file in files:
                if file.endswith('.md'):
                    path = Path(root) / file
                    self.process_file(path)
        
        if self.verbose:
            print(f"✓ Analysis complete: {len(self.results['graph'])} artifacts indexed")

    def process_file(self, path: Path):
        """Extract ID and dependencies from a single file"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Basic YAML extraction logic
                if content.startswith('---'):
                    parts = content.split('---')
                    if len(parts) >= 3:
                        yaml_part = parts[1]
                        lines = yaml_part.strip().split('\n')
                        metadata = {}
                        for line in lines:
                            if ':' in line:
                                k, v = line.split(':', 1)
                                metadata[k.strip()] = v.strip()
                        
                        art_id = metadata.get('id')
                        if art_id:
                            deps = metadata.get('dependencies', '[]')
                            # Clean up [FT-001, FT-002] format
                            deps = deps.strip('[]').split(',')
                            deps = [d.strip() for d in deps if d.strip()]
                            
                            self.results['graph'][art_id] = {
                                'file': str(path),
                                'dependencies': deps,
                                'parent': metadata.get('parent_goal') or metadata.get('parent_feat') or metadata.get('parent_uc')
                            }
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Error processing {path}: {e}")
    
    def generate_report(self):
        """Generate and display the report"""
        print("\n" + "="*50)
        print("REPORT")
        print("="*50)
        print(f"Target: {self.results.get('target')}")
        print(f"Status: {self.results.get('status')}")
        print(f"Findings: {len(self.results.get('findings', []))}")
        print("="*50 + "\n")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Dependency Analyzer"
    )
    parser.add_argument(
        'target',
        help='Target path to analyze or process'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )
    parser.add_argument(
        '--output', '-o',
        help='Output file path'
    )
    
    args = parser.parse_args()
    
    tool = DependencyAnalyzer(
        args.target,
        verbose=args.verbose
    )
    
    results = tool.run()
    
    if args.json:
        output = json.dumps(results, indent=2)
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
            print(f"Results written to {args.output}")
        else:
            print(output)

if __name__ == '__main__':
    main()
