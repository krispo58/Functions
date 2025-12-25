import os
import ast
import sys
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

class PythonCompiler:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.files: Dict[str, str] = {}
        self.dependencies: Dict[str, Set[str]] = {}
        self.module_map: Dict[str, str] = {}  # Maps module names to their aliases
        
    def find_python_files(self, exclude_patterns: List[str] = None) -> List[Path]:
        """Find all Python files in the project."""
        if exclude_patterns is None:
            exclude_patterns = ['__pycache__', '.venv', 'venv', '.git', 'tests']
        
        # Get the name of this compiler script to exclude it
        compiler_script = Path(__file__).name
        exclude_patterns.append(compiler_script)
        
        py_files = []
        for root, dirs, files in os.walk(self.project_root):
            # Remove excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_patterns]
            
            for file in files:
                if file.endswith('.py') and file not in exclude_patterns:
                    py_files.append(Path(root) / file)
        
        return py_files
    
    def parse_imports(self, content: str, file_path: Path) -> Set[str]:
        """Extract local imports from a Python file."""
        local_imports = set()
        
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        local_imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.level == 0 and node.module:  # Absolute import
                        local_imports.add(node.module.split('.')[0])
        except SyntaxError:
            print(f"Warning: Syntax error in {file_path}")
        
        return local_imports
    
    def remove_imports(self, content: str, local_modules: Set[str]) -> Tuple[str, Dict[str, str]]:
        """Remove local imports from the code and return mapping of module aliases.
        
        Returns:
            Tuple of (cleaned_content, alias_map) where alias_map maps 'alias' -> 'module'
        """
        tree = ast.parse(content)
        
        # Track which lines to keep and build alias mapping
        lines_to_remove = set()
        alias_map = {}  # Maps alias -> original module name
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]
                    if module_name in local_modules:
                        lines_to_remove.add(node.lineno)
                        # Track the alias used for this import
                        import_alias = alias.asname if alias.asname else alias.name
                        alias_map[import_alias] = alias.name
                        
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split('.')[0] in local_modules:
                    lines_to_remove.add(node.lineno)
                    # Track aliases for 'from x import y as z'
                    for alias in node.names:
                        import_alias = alias.asname if alias.asname else alias.name
                        full_name = f"{node.module}.{alias.name}"
                        alias_map[import_alias] = full_name
        
        # Rebuild content without local imports
        content_lines = content.split('\n')
        result = []
        for i, line in enumerate(content_lines, 1):
            if i not in lines_to_remove:
                result.append(line)
        
        return '\n'.join(result), alias_map
    
    def replace_module_references(self, content: str, alias_map: Dict[str, str]) -> str:
        """Replace module.ClassName references with just ClassName.
        
        For example, if we had 'import utils' and code uses 'utils.Helper',
        this will replace it with just 'Helper' since everything is in one namespace.
        """
        if not alias_map:
            return content
        
        # Sort by length (longest first) to avoid partial replacements
        sorted_aliases = sorted(alias_map.keys(), key=len, reverse=True)
        
        for alias in sorted_aliases:
            # Replace module.ClassName with ClassName
            # Use word boundaries to avoid replacing parts of other identifiers
            pattern = r'\b' + re.escape(alias) + r'\.([a-zA-Z_][a-zA-Z0-9_]*)'
            content = re.sub(pattern, r'\1', content)
        
        return content
    
    def remove_main_blocks(self, content: str) -> str:
        """Remove if __name__ == '__main__' blocks and main() function definitions."""
        tree = ast.parse(content)
        content_lines = content.split('\n')
        lines_to_remove = set()
        
        for node in tree.body:
            # Remove if __name__ == '__main__' blocks
            if isinstance(node, ast.If):
                # Check if it's a __name__ == '__main__' check
                if self._is_main_guard(node.test):
                    # Mark all lines in this block for removal
                    start_line = node.lineno
                    end_line = node.end_lineno
                    for line_num in range(start_line, end_line + 1):
                        lines_to_remove.add(line_num)
            
            # Remove main() function definitions
            elif isinstance(node, ast.FunctionDef) and node.name == 'main':
                start_line = node.lineno
                end_line = node.end_lineno
                for line_num in range(start_line, end_line + 1):
                    lines_to_remove.add(line_num)
        
        # Rebuild content without main blocks
        result = []
        for i, line in enumerate(content_lines, 1):
            if i not in lines_to_remove:
                result.append(line)
        
        return '\n'.join(result)
    
    def _is_main_guard(self, node) -> bool:
        """Check if an AST node is a __name__ == '__main__' check."""
        if isinstance(node, ast.Compare):
            # Check for __name__ == '__main__' or '__main__' == __name__
            if isinstance(node.left, ast.Name) and node.left.id == '__name__':
                if len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq):
                    if len(node.comparators) == 1:
                        comp = node.comparators[0]
                        if isinstance(comp, ast.Constant) and comp.value == '__main__':
                            return True
            elif isinstance(node.left, ast.Constant) and node.left.value == '__main__':
                if len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq):
                    if len(node.comparators) == 1:
                        comp = node.comparators[0]
                        if isinstance(comp, ast.Name) and comp.id == '__name__':
                            return True
        return False
        """Remove if __name__ == '__main__' blocks and main() function definitions."""
        tree = ast.parse(content)
        content_lines = content.split('\n')
        lines_to_remove = set()
        
        for node in tree.body:
            # Remove if __name__ == '__main__' blocks
            if isinstance(node, ast.If):
                # Check if it's a __name__ == '__main__' check
                if self._is_main_guard(node.test):
                    # Mark all lines in this block for removal
                    start_line = node.lineno
                    end_line = node.end_lineno
                    for line_num in range(start_line, end_line + 1):
                        lines_to_remove.add(line_num)
            
            # Remove main() function definitions
            elif isinstance(node, ast.FunctionDef) and node.name == 'main':
                start_line = node.lineno
                end_line = node.end_lineno
                for line_num in range(start_line, end_line + 1):
                    lines_to_remove.add(line_num)
        
        # Rebuild content without main blocks
        result = []
        for i, line in enumerate(content_lines, 1):
            if i not in lines_to_remove:
                result.append(line)
        
        return '\n'.join(result)
    
    def _is_main_guard(self, node) -> bool:
        """Check if an AST node is a __name__ == '__main__' check."""
        if isinstance(node, ast.Compare):
            # Check for __name__ == '__main__' or '__main__' == __name__
            if isinstance(node.left, ast.Name) and node.left.id == '__name__':
                if len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq):
                    if len(node.comparators) == 1:
                        comp = node.comparators[0]
                        if isinstance(comp, ast.Constant) and comp.value == '__main__':
                            return True
            elif isinstance(node.left, ast.Constant) and node.left.value == '__main__':
                if len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq):
                    if len(node.comparators) == 1:
                        comp = node.comparators[0]
                        if isinstance(comp, ast.Name) and comp.id == '__name__':
                            return True
        return False
    
    def get_module_name(self, file_path: Path) -> str:
        """Convert file path to module name."""
        relative = file_path.relative_to(self.project_root)
        parts = list(relative.parts[:-1]) + [relative.stem]
        if parts[-1] == '__init__':
            parts = parts[:-1]
        return '.'.join(parts) if parts else '__main__'
    
    def topological_sort(self, graph: Dict[str, Set[str]]) -> List[str]:
        """Sort modules by dependencies."""
        visited = set()
        result = []
        
        def visit(node):
            if node in visited:
                return
            visited.add(node)
            for dep in graph.get(node, set()):
                if dep in graph:  # Only visit if it's a local module
                    visit(dep)
            result.append(node)
        
        for node in graph:
            visit(node)
        
        return result
    
    def compile_project(self, exclude_patterns: List[str] = None, entry_point: str = None) -> str:
        """Compile all Python files into a single executable string.
        
        Args:
            exclude_patterns: List of directory/file patterns to exclude
            entry_point: Path to entry point file (e.g., 'main.py' or 'src/app.py')
                        Only this file will keep its main() and if __name__ == '__main__' blocks
        """
        py_files = self.find_python_files(exclude_patterns)
        
        # Determine the entry point module name
        entry_module = None
        if entry_point:
            entry_path = self.project_root / entry_point
            if entry_path.exists():
                entry_module = self.get_module_name(entry_path)
        
        # Read all files and build dependency graph
        module_contents = {}
        local_modules = set()
        
        for file_path in py_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            module_name = self.get_module_name(file_path)
            module_contents[module_name] = content
            local_modules.add(module_name)
            
            imports = self.parse_imports(content, file_path)
            self.dependencies[module_name] = imports
        
        # Sort modules by dependencies
        sorted_modules = self.topological_sort(self.dependencies)
        
        # Build combined code
        compiled_parts = []
        compiled_parts.append("# Compiled Python Project\n")
        compiled_parts.append("# This file was automatically generated\n\n")
        
        for module_name in sorted_modules:
            if module_name in module_contents:
                content = module_contents[module_name]
                
                # Remove local imports and get alias mapping
                cleaned_content, alias_map = self.remove_imports(content, local_modules)
                
                # Replace module.Class references with just Class
                cleaned_content = self.replace_module_references(cleaned_content, alias_map)
                
                # Remove main blocks unless this is the entry point
                if module_name != entry_module:
                    cleaned_content = self.remove_main_blocks(cleaned_content)
                
                compiled_parts.append(f"\n# === Module: {module_name} ===\n")
                compiled_parts.append(cleaned_content)
                compiled_parts.append("\n")
        
        return ''.join(compiled_parts)


# Example usage
if __name__ == "__main__":
    # Compile current directory with main.py as entry point
    compiler = PythonCompiler(".")
    
    # Exclude test files (compiler script auto-excluded)
    exclude = ['tests', 'test_*', '__pycache__', '.venv', "venv", ".git", "server"]
    
    # Specify entry point - only this file keeps main() and if __name__ == '__main__'
    compiled_code = compiler.compile_project(exclude, entry_point="client/main.py")
    
    # Save to file
    with open("compiled_project.py", "w", encoding='utf-8') as f:
        f.write(compiled_code)
    
    print(f"Compiled project")
    print("Output saved to: compiled_project.py")
    print(f"Entry point: main.py (preserves main blocks)")
    
    # Test compilation by checking syntax and collecting defined names
    print("\nValidating compilation...")
    try:
        tree = ast.parse(compiled_code)
        
        # Collect all defined classes, functions, and variables at module level
        defined_names = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                defined_names.append(f"class {node.name}")
            elif isinstance(node, ast.FunctionDef):
                defined_names.append(f"function {node.name}")
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defined_names.append(f"variable {target.id}")
        
        print(f"✓ Syntax valid!")
        print(f"✓ Found {len(defined_names)} top-level definitions")
        if defined_names[:10]:  # Show first 10
            print(f"  Sample: {', '.join(defined_names[:10])}")
        
        # Compile to bytecode to catch more errors
        compile(compiled_code, '<compiled>', 'exec')
        print("✓ Bytecode compilation successful!")
        
    except SyntaxError as e:
        print(f"✗ Syntax error: {e}")
    except Exception as e:
        print(f"✗ Compilation error: {e}")