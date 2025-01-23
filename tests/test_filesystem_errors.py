"""Tests for file system error handling."""
import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.tools.filesystem import FileSystemManager

@pytest.fixture
def temp_storage(tmp_path):
    """Create temporary storage directory."""
    return str(tmp_path)

@pytest.fixture
def fs_manager(temp_storage):
    """Create a test file system manager instance."""
    return FileSystemManager(storage_dir=temp_storage)

def test_file_not_found_handling(fs_manager):
    """Test handling of file not found errors."""
    # Test reading non-existent file
    with pytest.raises(FileNotFoundError):
        fs_manager.read_file("nonexistent.txt")
    
    # Test deleting non-existent file
    with pytest.raises(FileNotFoundError):
        fs_manager.delete_file("nonexistent.txt")
    
    # Test updating non-existent file
    with pytest.raises(FileNotFoundError):
        fs_manager.update_file("nonexistent.txt", "content")

def test_permission_error_handling(fs_manager, temp_storage):
    """Test handling of permission errors."""
    test_file = Path(temp_storage) / "test.txt"
    test_file.write_text("test content")
    
    # Make file read-only
    test_file.chmod(0o444)
    
    try:
        # Test writing to read-only file
        with pytest.raises(PermissionError):
            fs_manager.update_file("test.txt", "new content")
        
        # Test deleting read-only file
        with pytest.raises(PermissionError):
            fs_manager.delete_file("test.txt")
    finally:
        # Restore permissions for cleanup
        test_file.chmod(0o644)

def test_disk_space_error_handling(fs_manager):
    """Test handling of disk space errors."""
    with patch('pathlib.Path.write_text') as mock_write:
        mock_write.side_effect = OSError(28, "No space left on device")
        
        with pytest.raises(OSError) as exc_info:
            fs_manager.write_file("test.txt", "content")
        assert exc_info.value.errno == 28

def test_concurrent_access_handling(fs_manager):
    """Test handling of concurrent file access."""
    test_file = "test.txt"
    
    # Create initial file
    fs_manager.write_file(test_file, "initial content")
    
    # Simulate concurrent access
    with patch('pathlib.Path.write_text') as mock_write:
        mock_write.side_effect = [
            OSError(11, "Resource temporarily unavailable"),  # First attempt fails
            None  # Second attempt succeeds
        ]
        
        fs_manager.update_file(test_file, "new content")
        
        # Verify retry behavior
        assert mock_write.call_count == 2

def test_invalid_path_handling(fs_manager):
    """Test handling of invalid file paths."""
    invalid_paths = [
        "../outside.txt",  # Path traversal
        "//invalid//path",  # Invalid path format
        "\0malicious.txt",  # Null byte injection
        "com1",  # Reserved name on Windows
        " ",  # Empty path
        "a" * 256  # Path too long
    ]
    
    for path in invalid_paths:
        with pytest.raises((ValueError, OSError)):
            fs_manager.write_file(path, "content")

def test_file_corruption_handling(fs_manager):
    """Test handling of corrupted files."""
    test_file = "test.txt"
    
    # Write valid file
    fs_manager.write_file(test_file, "valid content")
    
    # Simulate corruption
    with patch('pathlib.Path.read_text') as mock_read:
        mock_read.side_effect = UnicodeDecodeError('utf-8', b'invalid', 0, 1, 'invalid byte')
        
        with pytest.raises(UnicodeDecodeError):
            fs_manager.read_file(test_file)

def test_directory_error_handling(fs_manager, temp_storage):
    """Test handling of directory-related errors."""
    test_dir = Path(temp_storage) / "test_dir"
    
    # Test creating directory that already exists
    test_dir.mkdir()
    with pytest.raises(FileExistsError):
        fs_manager.create_directory(str(test_dir))
    
    # Test creating directory with invalid parent
    invalid_dir = test_dir / "subdir" / "file.txt"
    with pytest.raises(FileNotFoundError):
        fs_manager.write_file(str(invalid_dir), "content")
    
    # Test removing non-empty directory
    (test_dir / "file.txt").write_text("content")
    with pytest.raises(OSError):
        fs_manager.delete_directory(str(test_dir))

def test_symlink_handling(fs_manager, temp_storage):
    """Test handling of symbolic links."""
    test_file = Path(temp_storage) / "test.txt"
    test_file.write_text("content")
    
    symlink = Path(temp_storage) / "link.txt"
    symlink.symlink_to(test_file)
    
    try:
        # Test reading through symlink
        content = fs_manager.read_file("link.txt")
        assert content == "content"
        
        # Test modifying through symlink
        fs_manager.update_file("link.txt", "new content")
        assert test_file.read_text() == "new content"
        
        # Test deleting symlink
        fs_manager.delete_file("link.txt")
        assert not symlink.exists()
        assert test_file.exists()
    finally:
        # Cleanup
        if symlink.exists():
            symlink.unlink() 