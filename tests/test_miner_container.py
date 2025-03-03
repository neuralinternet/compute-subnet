import pytest
from unittest.mock import patch, MagicMock

from neurons.Miner.container import (
    check_container,
    pause_container,
    unpause_container,
    container_name,
    container_name_test,
    retrieve_allocation_key,
    get_docker,
    kill_container
)

def test_check_container_running():
    """
    Test container running status check.
    
    Verifies that:
    - Docker client and container are properly mocked
    - Container name matches expected format
    - Container status is correctly identified as running
    """
    mock_client = MagicMock()
    mock_container1 = MagicMock()
    mock_container1.name = container_name
    mock_container1.status = "running"
    
    with patch('neurons.Miner.container.get_docker', return_value=(mock_client, [mock_container1])):
        result = check_container()
        assert result is True

def test_check_container_test_running():
    """
    Test test container running status check.
    
    Verifies that:
    - Test container is properly identified
    - Container status is correctly identified as running
    """
    mock_client = MagicMock()
    mock_container_test = MagicMock()
    mock_container_test.name = container_name_test
    mock_container_test.status = "running"
    
    with patch('neurons.Miner.container.get_docker', return_value=(mock_client, [mock_container_test])):
        result = check_container()
        assert result is True

def test_check_container_not_running():
    """
    Test container not running status check.
    
    Verifies that:
    - System correctly identifies when target container is not running
    - Returns False when container is not found
    """
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.name = "other_container"
    mock_container.status = "running"
    
    with patch('neurons.Miner.container.get_docker', return_value=(mock_client, [mock_container])):
        result = check_container()
        assert result is False

def test_check_container_exception():
    """
    Test container check exception handling.
    
    Verifies that:
    - System properly handles Docker client exceptions
    - Returns False when an exception occurs
    """
    with patch('neurons.Miner.container.get_docker', side_effect=Exception("Test error")):
        result = check_container()
        assert result is False

# Tests for pause_container
def test_pause_container_success():
    """
    Test successful container pause operation.
    
    Verifies that:
    - Allocation key is properly retrieved
    - Container is found and paused
    - Operation returns success status
    """
    mock_key = "test_public_key"
    
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.name = f"prefix_{container_name}_suffix"
    mock_containers = [mock_container]
    
    with patch('neurons.Miner.container.retrieve_allocation_key', return_value=mock_key):
        with patch('neurons.Miner.container.get_docker', return_value=(mock_client, mock_containers)):
            result = pause_container("test_public_key")
            
            mock_container.pause.assert_called_once()
            assert result == {"status": True}

def test_pause_container_no_allocation_key():
    """
    Test pause container with missing allocation key.
    
    Verifies that:
    - System handles missing allocation key gracefully
    - Returns failure status when key is not found
    """
    with patch('neurons.Miner.container.retrieve_allocation_key', return_value=None):
        result = pause_container("test_public_key")
        assert result == {"status": False}

def test_pause_container_key_mismatch():
    """
    Test pause container with mismatched allocation key.
    
    Verifies that:
    - System properly handles mismatched allocation keys
    - Returns failure status for invalid keys
    """
    mock_key = "valid_key"
    
    with patch('neurons.Miner.container.retrieve_allocation_key', return_value=mock_key):
        result = pause_container("invalid_key")
        assert "status" in result
        assert result["status"] == False

def test_pause_container_not_found():
    """
    Test pause container when target container is not found.
    
    Verifies that:
    - System handles missing container gracefully
    - Returns failure status when container is not found
    """
    mock_key = "test_public_key"
    
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.name = "different_container"
    mock_containers = [mock_container]
    
    with patch('neurons.Miner.container.retrieve_allocation_key', return_value=mock_key):
        with patch('neurons.Miner.container.get_docker', return_value=(mock_client, mock_containers)):
            result = pause_container("test_public_key")
            assert result == {"status": False}

def test_pause_container_exception():
    """
    Test pause container exception handling.
    
    Verifies that:
    - System properly handles Docker client exceptions
    - Returns failure status when an exception occurs
    """
    mock_key = "test_public_key"
    
    with patch('neurons.Miner.container.retrieve_allocation_key', return_value=mock_key):
        with patch('neurons.Miner.container.get_docker', side_effect=Exception("Test error")):
            result = pause_container("test_public_key")
            assert result == {"status": False}

# Tests for unpause_container
def test_unpause_container_success():
    """
    Test successful container unpause operation.
    
    Verifies that:
    - Allocation key is properly retrieved
    - Container is found and unpaused
    - Operation returns success status
    """
    mock_key = "test_public_key"
    
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.name = f"prefix_{container_name}_suffix"
    mock_containers = [mock_container]
    
    with patch('neurons.Miner.container.retrieve_allocation_key', return_value=mock_key):
        with patch('neurons.Miner.container.get_docker', return_value=(mock_client, mock_containers)):
            result = unpause_container("test_public_key")
            
            mock_container.unpause.assert_called_once()
            assert result == {"status": True}

def test_unpause_container_no_allocation_key():
    """
    Test unpause container with missing allocation key.
    
    Verifies that:
    - System handles missing allocation key gracefully
    - Returns failure status when key is not found
    """
    with patch('neurons.Miner.container.retrieve_allocation_key', return_value=None):
        result = unpause_container("test_public_key")
        assert result == {"status": False}

def test_unpause_container_key_mismatch():
    """
    Test unpause container with mismatched allocation key.
    
    Verifies that:
    - System properly handles mismatched allocation keys
    - Returns failure status for invalid keys
    """
    mock_key = "valid_key"
    
    with patch('neurons.Miner.container.retrieve_allocation_key', return_value=mock_key):
        result = unpause_container("invalid_key")
        assert "status" in result
        assert result["status"] == False

def test_unpause_container_not_found():
    """
    Test unpause container when target container is not found.
    
    Verifies that:
    - System handles missing container gracefully
    - Returns failure status when container is not found
    """
    mock_key = "test_public_key"
    
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.name = "different_container"
    mock_containers = [mock_container]
    
    with patch('neurons.Miner.container.retrieve_allocation_key', return_value=mock_key):
        with patch('neurons.Miner.container.get_docker', return_value=(mock_client, mock_containers)):
            result = unpause_container("test_public_key")
            assert result == {"status": False}

def test_unpause_container_exception():
    """
    Test unpause container exception handling.
    
    Verifies that:
    - System properly handles Docker client exceptions
    - Returns failure status when an exception occurs
    """
    mock_key = "test_public_key"
    
    with patch('neurons.Miner.container.retrieve_allocation_key', return_value=mock_key):
        with patch('neurons.Miner.container.get_docker', side_effect=Exception("Test error")):
            result = unpause_container("test_public_key")
            assert result == {"status": False}

def test_get_docker_success():
    """
    Test successful Docker client initialization and container listing.
    
    Verifies that:
    - Docker client is properly initialized
    - Container list is successfully retrieved
    - List method is called with correct parameters
    - Returned values match expected mock objects
    """
    mock_client = MagicMock()
    mock_containers = [MagicMock(), MagicMock()]
    
    mock_client.containers.list.return_value = mock_containers
    
    with patch('docker.from_env', return_value=mock_client):
        client, containers = get_docker()
        
        assert client == mock_client
        assert containers == mock_containers
        mock_client.containers.list.assert_called_once_with(all=True)

def test_get_docker_exception():
    """
    Test Docker client initialization failure.
    
    Verifies that:
    - Exception from docker.from_env() is properly propagated
    - System fails gracefully when Docker client cannot be initialized
    """
    with patch('docker.from_env', side_effect=Exception("Docker error")):
        with pytest.raises(Exception):
            get_docker()
            
def test_get_docker_list_exception():
    """
    Test container listing failure.
    
    Verifies that:
    - Exception from containers.list() is properly propagated
    - System fails gracefully when container list cannot be retrieved
    """
    mock_client = MagicMock()
    
    mock_client.containers.list.side_effect = Exception("List error")
    
    with patch('docker.from_env', return_value=mock_client):
        with pytest.raises(Exception):
            get_docker()

def test_kill_container_test_running():
    """
    Test killing a running test container.
    
    Verifies that:
    - Container is properly identified as test container
    - Kill command is executed with correct parameters
    - Container is waited for and removed
    - Dangling images are pruned
    - Operation returns success status
    """
    mock_client = MagicMock()
    mock_container_test = MagicMock()
    mock_container_test.name = container_name_test
    mock_container_test.status = "running"
    mock_containers = [mock_container_test]
    
    mock_client.images.prune = MagicMock()
    
    with patch('neurons.Miner.container.get_docker', return_value=(mock_client, mock_containers)):
        result = kill_container()
        
        mock_container_test.exec_run.assert_called_once_with(cmd="kill -15 1")
        mock_container_test.wait.assert_called_once()
        mock_container_test.remove.assert_called_once()
        mock_client.images.prune.assert_called_once_with(filters={"dangling": True})
        assert result is True

def test_kill_container_test_not_running():
    """
    Test handling of non-running test container.
    
    Verifies that:
    - Container is identified as not running
    - Kill command is not executed
    - Container is removed without waiting
    - Dangling images are pruned
    - Operation returns success status
    """
    mock_client = MagicMock()
    mock_container_test = MagicMock()
    mock_container_test.name = container_name_test
    mock_container_test.status = "exited"
    mock_containers = [mock_container_test]
    
    mock_client.images.prune = MagicMock()
    
    with patch('neurons.Miner.container.get_docker', return_value=(mock_client, mock_containers)):
        result = kill_container()
        
        mock_container_test.exec_run.assert_not_called()
        mock_container_test.wait.assert_not_called()
        mock_container_test.remove.assert_called_once()
        mock_client.images.prune.assert_called_once_with(filters={"dangling": True})
        assert result is True

def test_kill_container_regular_running():
    """
    Test killing a running regular container.
    
    Verifies that:
    - Container is properly identified as regular container
    - Kill command is executed with correct parameters
    - Container is waited for and removed
    - Dangling images are pruned
    - Operation returns success status
    """
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.name = container_name
    mock_container.status = "running"
    mock_containers = [mock_container]
    
    mock_client.images.prune = MagicMock()
    
    with patch('neurons.Miner.container.get_docker', return_value=(mock_client, mock_containers)):
        result = kill_container()
        
        mock_container.exec_run.assert_called_once_with(cmd="kill -15 1")
        mock_container.wait.assert_called_once()
        mock_container.remove.assert_called_once()
        mock_client.images.prune.assert_called_once_with(filters={"dangling": True})
        assert result is True

def test_kill_container_regular_not_running():
    """
    Test handling of non-running regular container.
    
    Verifies that:
    - Container is identified as not running
    - Kill command is not executed
    - Container is removed without waiting
    - Dangling images are pruned
    - Operation returns success status
    """
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.name = container_name
    mock_container.status = "exited"
    mock_containers = [mock_container]
    
    mock_client.images.prune = MagicMock()
    
    with patch('neurons.Miner.container.get_docker', return_value=(mock_client, mock_containers)):
        result = kill_container()
        
        mock_container.exec_run.assert_not_called()
        mock_container.wait.assert_not_called()
        mock_container.remove.assert_called_once()
        mock_client.images.prune.assert_called_once_with(filters={"dangling": True})
        assert result is True

def test_kill_container_priority():
    """
    Test container kill priority (test container over regular).
    
    Verifies that:
    - Test container is prioritized over regular container
    - Only test container is killed and removed
    - Regular container is left untouched
    - Dangling images are pruned
    - Operation returns success status
    """
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.name = container_name
    mock_container.status = "running"
    
    mock_container_test = MagicMock()
    mock_container_test.name = container_name_test
    mock_container_test.status = "running"
    
    mock_containers = [mock_container, mock_container_test]
    
    mock_client.images.prune = MagicMock()
    
    with patch('neurons.Miner.container.get_docker', return_value=(mock_client, mock_containers)):
        result = kill_container()
        
        mock_container_test.exec_run.assert_called_once_with(cmd="kill -15 1")
        mock_container_test.wait.assert_called_once()
        mock_container_test.remove.assert_called_once()
        
        mock_container.exec_run.assert_not_called()
        mock_container.wait.assert_not_called()
        mock_container.remove.assert_not_called()
        
        mock_client.images.prune.assert_called_once_with(filters={"dangling": True})
        assert result is True

def test_kill_container_not_found():
    """
    Test handling when target containers are not found.
    
    Verifies that:
    - No kill commands are executed
    - No containers are removed
    - Dangling images are still pruned
    - Operation returns success status
    """
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.name = "other_container"
    mock_containers = [mock_container]
    
    mock_client.images.prune = MagicMock()
    
    with patch('neurons.Miner.container.get_docker', return_value=(mock_client, mock_containers)):
        result = kill_container()
        
        mock_container.exec_run.assert_not_called()
        mock_container.wait.assert_not_called()
        mock_container.remove.assert_not_called()
        
        mock_client.images.prune.assert_called_once_with(filters={"dangling": True})
        assert result is True

def test_kill_container_exception():
    """
    Test exception handling during container kill operation.
    
    Verifies that:
    - Docker client exceptions are properly handled
    - Operation returns failure status when exception occurs
    """
    with patch('neurons.Miner.container.get_docker', side_effect=Exception("Test error")):
        result = kill_container()
        assert result is False