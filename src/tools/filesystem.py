"""
File system operations for Anthropic CLI tools.
"""
import os
import time
import shutil
from pathlib import Path
from typing import List, Optional, Union

class FileSystemManager:
    """Manages file system operations with error handling."""
    
    def __init__(self, storage_dir: Union[str, Path]):
        """Initialize with a base storage directory.
        
        Args:
            storage_dir: Base directory for all file operations
        """
        self.storage_dir = Path(storage_dir).resolve()
        if not self.storage_dir.exists():
            self.storage_dir.mkdir(parents=True)
    
    def _validate_path(self, path: Union[str, Path]) -> Path:
        """Validate and normalize a path."""
        if not path or str(path).isspace():
            raise ValueError("Path cannot be empty or whitespace")
            
        path = Path(path)
        if path.is_absolute():
            try:
                path = path.relative_to(self.storage_dir)
            except ValueError:
                raise ValueError(f"Path {path} must be within storage directory")
                
        # Check for path traversal
        if '..' in str(path):
            raise ValueError("Path traversal not allowed")
            
        # Check for invalid characters
        invalid_chars = '\0<>:"|?*'
        if any(c in str(path) for c in invalid_chars):
            raise ValueError(f"Path contains invalid characters: {invalid_chars}")
            
        # Check path length
        if len(str(path)) > 255:
            raise OSError("Path too long")
            
        return self.storage_dir / path
    
    def read_file(self, path: Union[str, Path]) -> str:
        """Read file contents."""
        path = self._validate_path(path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not os.access(path, os.R_OK):
            raise PermissionError(f"Permission denied: {path}")
        return path.read_text()
    
    def write_file(self, path: Union[str, Path], content: str) -> None:
        """Write content to file."""
        path = self._validate_path(path)
        if not path.parent.exists():
            path.parent.mkdir(parents=True)
        if path.exists() and not os.access(path, os.W_OK):
            raise PermissionError(f"Permission denied: {path}")
        path.write_text(content)
    
    def update_file(self, path: Union[str, Path], content: str, retry_count: int = 3) -> None:
        """Update an existing file."""
        path = self._validate_path(path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not os.access(path, os.W_OK):
            raise PermissionError(f"Permission denied: {path}")
            
        for attempt in range(retry_count):
            try:
                path.write_text(content)
                return
            except BlockingIOError:
                if attempt < retry_count - 1:
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                    continue
                raise
    
    def delete_file(self, path: Union[str, Path]) -> None:
        """Delete a file."""
        path = self._validate_path(path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not os.access(path, os.W_OK):
            raise PermissionError(f"Permission denied: {path}")
            
        if path.is_symlink():
            target = path.resolve()
            if target.exists() and target.is_relative_to(self.storage_dir):
                # Preserve target file if it's within storage_dir
                content = target.read_text()
                path.unlink()
                target.write_text(content)
            else:
                path.unlink()
        else:
            path.unlink()
    
    def create_directory(self, path: Union[str, Path]) -> None:
        """Create a directory."""
        path = self._validate_path(path)
        if not path.parent.exists():
            raise FileNotFoundError(f"Parent directory does not exist: {path.parent}")
        if path.exists():
            if not path.is_dir():
                raise FileExistsError(f"Path exists and is not a directory: {path}")
        else:
            path.mkdir()
    
    def delete_directory(self, path: Union[str, Path]) -> None:
        """Delete a directory."""
        path = self._validate_path(path)
        if not path.exists():
            raise FileNotFoundError(f"Directory not found: {path}")
        if not path.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {path}")
        if not os.access(path, os.W_OK):
            raise PermissionError(f"Permission denied: {path}")
        shutil.rmtree(path)

class FileSystemTools:
    """Tools for file system operations."""
    
    @staticmethod
    def read_file(file_path: Union[str, Path], encoding: str = 'utf-8') -> str:
        """
        Read contents of a file.
        
        Args:
            file_path: Path to the file
            encoding: File encoding (default: utf-8)
            
        Returns:
            str: Contents of the file
            
        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If file can't be read
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        try:
            with open(path, 'r', encoding=encoding) as f:
                return f.read()
        except IOError as e:
            raise IOError(f"Error reading file {file_path}: {str(e)}")
    
    @staticmethod
    def write_file(
        file_path: Union[str, Path],
        content: str,
        encoding: str = 'utf-8',
        create_dirs: bool = True
    ) -> None:
        """
        Write content to a file.
        
        Args:
            file_path: Path to the file
            content: Content to write
            encoding: File encoding (default: utf-8)
            create_dirs: Create parent directories if they don't exist
            
        Raises:
            IOError: If file can't be written
        """
        path = Path(file_path)
        
        if create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)
            
        try:
            with open(path, 'w', encoding=encoding) as f:
                f.write(content)
        except IOError as e:
            raise IOError(f"Error writing to file {file_path}: {str(e)}")
    
    @staticmethod
    def list_directory(
        directory: Union[str, Path],
        pattern: Optional[str] = None,
        recursive: bool = False
    ) -> List[Path]:
        """
        List contents of a directory.
        
        Args:
            directory: Path to the directory
            pattern: Optional glob pattern to filter files
            recursive: Whether to list subdirectories recursively
            
        Returns:
            List[Path]: List of paths in the directory
            
        Raises:
            NotADirectoryError: If path is not a directory
            FileNotFoundError: If directory doesn't exist
        """
        path = Path(directory)
        
        if not path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        if not path.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")
            
        try:
            if recursive:
                if pattern:
                    return list(path.rglob(pattern))
                return list(path.rglob("*"))
            else:
                if pattern:
                    return list(path.glob(pattern))
                return list(path.glob("*"))
        except Exception as e:
            raise IOError(f"Error listing directory {directory}: {str(e)}") 