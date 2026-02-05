import ast
from pathlib import Path


class SkeletonTransformer(ast.NodeTransformer):
    """Оставляет только сигнатуры, декораторы и докстринги."""

    def visit_FunctionDef(self, node):
        docstring = ast.get_docstring(node)
        new_body = []
        if docstring:
            new_body.append(ast.Expr(value=ast.Constant(value=docstring)))
        new_body.append(ast.Expr(value=ast.Constant(value=...)))
        node.body = new_body
        return node

    def visit_AsyncFunctionDef(self, node):
        return self.visit_FunctionDef(node)

    def visit_ClassDef(self, node):
        self.generic_visit(node)
        return node


class CodeProcessor:
    @staticmethod
    def is_binary(file_path: Path) -> bool:
        try:
            with open(file_path, "tr", encoding="utf-8") as f:
                f.read(1024)
                return False
        except:
            return True

    @staticmethod
    def process_file(file_path: Path, skeleton_mode: bool) -> str:
        if CodeProcessor.is_binary(file_path):
            return f"# [Binary File Skipped: {file_path.name}]"

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"# [Error reading file: {e}]"

        if not skeleton_mode:
            return content

        if file_path.suffix not in (".py", ".pyw"):
            return content

        try:
            tree = ast.parse(content)
            transformer = SkeletonTransformer()
            new_tree = transformer.visit(tree)
            ast.fix_missing_locations(new_tree)
            return ast.unparse(new_tree)
        except Exception as e:
            return content + f"\n# [AST Error: {e}]"
