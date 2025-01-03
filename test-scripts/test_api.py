import json
import time
import pytest
import httpx
import allure
import os


class TestAPI:
    uuid = ""
    cert = (os.getcwd() + "/../cert/client.crt", os.getcwd() + "/../cert/client.key")
    ca = (os.getcwd() + "/../cert/ca.cer")
    url = "https://127.0.0.1:8093"
    hotkey = "5C4wGPrkgTJJvqkqiy7Yh5QDwjV14exeyJKvDjX64fwbsft6"

    @allure.testcase("TC-1: Test / endpoint")
    def test_read_root(self):
        """
        Test / endpoint
        """

        response = httpx.get(url=self.url, timeout=10, cert=self.cert, verify=self.ca)

        assert response.status_code == 200
        assert response.json() == {
            "message": "Welcome to Compute Subnet Allocation API, Please access the API via endpoint."
        }

    @allure.testcase("TC-2-1: Test list all runs endpoint")
    def test_list_all_runs(self):
        """
        Test /list/all_runs
        """
        response = httpx.post(
            url=self.url + "/list/all_runs", data={}, verify=self.ca, timeout=10, cert=self.cert)
        assert response.status_code == 200
        resp_body = response.json()
        print(resp_body)
        assert resp_body["success"] == True
        assert resp_body["message"] == "List run resources successfully."
        assert len(resp_body["data"]) > 0

    @allure.testcase("TC-2-2: Test list all runs endpoint with hotkey")
    def test_list_all_runs_hotkey(self):
        """
        Test /list/all_runs with hotkey
        """
        response = httpx.post(
            url=self.url + "/list/all_runs?hotkey=" + self.hotkey,
            data={}, verify=self.ca, timeout=10, cert=self.cert)
        assert response.status_code == 200
        resp_body = response.json()
        print(resp_body)
        assert resp_body["success"] == True
        assert resp_body["message"] == "List run resources successfully."
        assert len(resp_body["data"]) > 0

    @allure.testcase("TC-2-3: Test list all runs endpoint with pagination")
    def test_list_all_runs_pagination(self):
        """
        Test /list/all_runs with pagination
        """
        response = httpx.post(
            url=self.url + "/list/all_runs?page_size=2&page_number=1",
            data={}, verify=self.ca, timeout=10, cert=self.cert)
        assert response.status_code == 200
        resp_body = response.json()
        print(resp_body)
        assert resp_body["success"] == True
        assert resp_body["message"] == "List run resources successfully."
        assert len(resp_body["data"]) > 0

    @allure.testcase("TC-3-1: Test list specs endpoint")
    def test_list_specs(self):
        """
        Test /list/specs
        """
        response = httpx.post(
            url=self.url + "/list/specs", data={}, verify=self.ca, timeout=10, cert=self.cert
        )
        assert response.status_code == 200
        resp_body = response.json()
        print(resp_body)
        assert resp_body["success"] == True
        assert resp_body["message"] == "List specs successfully"
        assert len(resp_body["data"]) > 0

    @allure.testcase("TC-3-2: Test list specs endpoint with hotkey")
    def test_list_specs_hotkey(self):
        """
        Test /list/specs with hotkey
        """
        response = httpx.post(
            url=self.url + "/list/specs?hotkey=" + self.hotkey,
            data={}, verify=self.ca, timeout=10, cert=self.cert,
        )
        assert response.status_code == 200
        resp_body = response.json()
        print(resp_body)
        assert resp_body["success"] == True
        assert resp_body["message"] == "List specs successfully"
        assert len(resp_body["data"]) > 0

    @allure.testcase("TC-3-3: Test list specs endpoint with pagination")
    def test_list_specs_pagination(self):
        """
        Test /list/specs with pagination
        """
        response = httpx.post(
            url=self.url + "/list/specs?page_size=2&page_number=1",
            data={}, verify=self.ca, timeout=10, cert=self.cert,
        )
        assert response.status_code == 200
        resp_body = response.json()
        print(resp_body)
        assert resp_body["success"] == True
        assert resp_body["message"] == "List specs successfully"
        assert len(resp_body["data"]) > 0

    @allure.testcase("TC-4-1: Test list runs by name endpoint - pass scenario")
    def test_list_run_by_name_pass(self):
        """
        Test /list/specs
        """
        response = httpx.post(
            url=self.url + "/list/run_by_name?run_name=miner-" + self.hotkey,
            verify=self.ca, timeout=10, cert=self.cert
        )
        assert response.status_code == 200
        resp_body = response.json()
        print(resp_body)
        assert resp_body["success"] == True
        assert resp_body["message"] == "List run by name"
        assert len(resp_body["data"]) > 0

    @allure.testcase("TC-4-2: Test list runs by name endpoint - fail scenario")
    def test_list_run_by_name_fail(self):
        """
        Test /list/specs
        """
        response = httpx.post(
            url=self.url + "/list/run_by_name?run_name=miner", verify=self.ca, timeout=10,
            cert=self.cert
        )
        assert response.status_code == 200
        resp_body = response.json()
        print(resp_body)
        assert resp_body["success"] == True
        assert resp_body["message"] == "No run available"
        assert len(resp_body["data"]) == 0

    @allure.testcase("TC-5-1: Test list avaliable endpoint - rent scenario")
    def test_list_available_rent_on(self):
        """
        Test /list/available with rent on
        """
        response = httpx.post(
            url=self.url + "/list/available?rent_status=true", verify=self.ca, timeout=10, cert=self.cert
        )
        assert response.status_code == 200
        resp_body = response.json()
        print(resp_body)
        assert resp_body["success"] == True
        assert resp_body["message"] == "List rented miners"
        if len(resp_body["data"]) > 0:
            print(resp_body["data"])
        else:
            print("No rented miners available")

    @allure.testcase("TC-5-2: Test list avaliable endpoint - rent off scenario")
    def test_list_available_rent_off(self):
        """
        Test /list/available with rent off
        """
        response = httpx.post(
            url=self.url + "/list/available?rent_status=false", verify=self.ca, timeout=10, cert=self.cert
        )
        assert response.status_code == 200
        resp_body = response.json()
        print(resp_body)
        assert resp_body["success"] == True
        assert resp_body["message"] == "List available miners"
        assert len(resp_body["data"]) > 0

    @allure.testcase("TC-5-3: Test list avaliable endpoint with pagination")
    def test_list_available_pagination(self):
        """
        Test /list/available with pagination
        """
        response = httpx.post(
            url=self.url + "/list/available?page_size=2&page_number=1", verify=self.ca, timeout=10, cert=self.cert
        )
        assert response.status_code == 200
        resp_body = response.json()
        print(resp_body)
        assert resp_body["success"] == True
        assert resp_body["message"] == "List available miners"
        assert len(resp_body["data"]) > 0

    @allure.testcase("TC-6: Test list allocated hotkeys endpoint")
    def test_list_allocated_hotkeys(self):
        """
        Test /list/allocated_hotkeys
        """
        response = httpx.post(
            url=self.url + "/list/allocated_hotkeys", data={}, verify=self.ca, timeout=10, cert=self.cert
        )
        assert response.status_code == 200
        resp_body = response.json()
        print(resp_body)
        assert resp_body["success"] == True
        if len(resp_body["data"]) > 0:
            assert resp_body["message"] == "List allocated hotkeys"
            print(resp_body["data"])
        elif len(resp_body["data"]) == 0:
            assert (
                    resp_body["message"]
                    == "No validator with allocated info in the project opencompute."
            )
            assert resp_body["data"] == {}

    @allure.testcase("TC-7: Test list allocations endpoint")
    def test_list_allocations_sql(self):
        """
        Test /list/allocations_sql
        """
        response = httpx.post(
            url=self.url + "/list/allocations_sql", data={}, verify=self.ca, timeout=10, cert=self.cert
        )
        if response.status_code == 200:
            assert response.status_code == 200
            resp_body = response.json()
            print(resp_body)
            assert resp_body["success"] == True
            if len(resp_body["data"]) > 0:
                assert resp_body["message"] == "List allocations successfully."
                print(resp_body["data"])
        else:
            assert response.status_code == 404
            resp_body = response.json()
            print(resp_body)
            assert resp_body["success"] == False
            assert resp_body["message"] == "No resources found."

    @allure.testcase("TC-8-1: Test list resource sql endpoint with found resources")
    def test_list_resource_sql_found(self):
        """
        Test /list/resource_sql
        """
        response = httpx.post(
            url=self.url + "/list/resources_sql",
            json={"gpu_name": "4090", "cpu_count_min": 1},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            verify=self.ca,
            timeout=10,
            cert=self.cert
        )
        assert response.status_code == 200
        resp_body = response.json()
        assert resp_body["success"] == True
        assert resp_body["message"] == "List resources successfully"
        print(resp_body["data"])

    @allure.testcase("TC-8-2: Test list resource sql endpoint with not found resources")
    def test_list_resource_sql_not_found(self):
        """
        Test /list/resource_sql
        """
        response = httpx.post(
            url=self.url + "/list/resources_sql",
            json={"gpu_name": "h2000", "cpu_count_min": 1},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            verify=self.ca,
            timeout=10,
            cert=self.cert
        )
        assert response.status_code == 200
        resp_body = response.json()
        assert resp_body["success"] == True
        assert resp_body["message"] == "List resources successfully"
        assert resp_body["data"] == {'page_items': [], 'page_number': 1, 'page_size': 0, 'next_page_number': None}
        print(resp_body["data"])

    @allure.testcase("TC-8-3: Test list resource sql endpoint with pagination")
    def test_list_resource_sql_pagination(self):
        """
        Test /list/resource_sql
        """
        response = httpx.post(
            url=self.url + "/list/resources_sql?stats=false&page_size=2&page_number=1",
            json={},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            verify=self.ca,
            timeout=10,
            cert=self.cert
        )
        assert response.status_code == 200
        resp_body = response.json()
        assert resp_body["success"] == True
        assert resp_body["message"] == "List resources successfully"
        print(resp_body["data"])

    @allure.testcase("TC-8-4: Test list resource sql endpoint with statistics")
    def test_list_resource_sql_stats(self):
        """
        Test /list/resource_sql
        """
        response = httpx.post(
            url=self.url + "/list/resources_sql?stats=true",
            json={},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            verify=self.ca,
            timeout=10,
            cert=self.cert
        )
        assert response.status_code == 200
        resp_body = response.json()
        assert resp_body["success"] == True
        assert resp_body["message"] == "List resources successfully"
        print(resp_body["data"])

    @allure.testcase("TC-9: Test allocation spec endpoint")
    def test_service_allocate_spec(self):
        """
        Test /service/allocate_spec
        """
        response = httpx.post(
            url=self.url + "/service/allocate_spec",
            json={
                "requirements": {
                    "cpu_count": 1,
                    "gpu_type": "4050",
                    "gpu_size": 3,
                    "ram": 1,
                    "hard_disk": 1,
                    "timeline": 90
                },
                "docker_requirement": {
                    "base_image": "ubuntu",
                    "ssh_key": "",
                    "ssh_port": 4444,
                    "volume_path": "/tmp",
                    "dockerfile": ""
                }
            }
            ,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=10,
            verify=self.ca,
            cert=self.cert
        )
        assert response.status_code == 200
        resp_body = response.json()
        assert resp_body["success"] == True
        assert resp_body["message"] == "Resource was successfully allocated"
        assert resp_body["data"]["resource"] == "nvidia geforce rtx 4050 laptop gpu"
        TestAPI.uuid = resp_body["data"]["uuid_key"]
        print(resp_body["data"])

    @allure.testcase("TC-10-1: Test deallocation spec endpoint")
    @pytest.mark.depends(on=["test_service_allocate_spec"])
    def test_service_deallocation_spec(self):
        """
        Test /service/deallocate
        """
        response = httpx.post(
            url=self.url + "/service/deallocate?hotkey=" + self.hotkey + "&uuid_key=" + TestAPI.uuid,
            timeout=15,
            verify=self.ca,
            cert=self.cert
        )
        assert response.status_code == 200
        resp_body = response.json()
        assert resp_body["success"] == True
        assert resp_body["message"] == "Resource deallocated successfully."

    @allure.testcase("TC-10-2: Test de-allocation spec with not found endpoint")
    def test_service_deallocation_error(self):
        """
        Test /service/deallocate
        """
        response = httpx.post(
            url=self.url + "/service/deallocate?hotkey=miner-aaa&uuid_key=1234",
            timeout=10,
            verify=self.ca,
            cert=self.cert
        )
        assert response.status_code == 404
        resp_body = response.json()
        assert resp_body["success"] == False
        assert resp_body["message"] == "No allocation details found for the provided hotkey."
        print(resp_body["err_detail"])

    @allure.testcase("TC-11-1: Test allocation hotkey endpoint")
    @pytest.mark.depends(on=["test_service_deallocation_spec"])
    def test_service_allocate_hotkey(self):
        """
        Test /service/allocate_spec
        """
        response = httpx.post(
            url=self.url + "/service/allocate_hotkey?hotkey=" + self.hotkey,
            json={
                "base_image": "ubuntu",
                "ssh_key": "",
                "ssh_port": 4444,
                "volume_path": "/tmp",
                "dockerfile": ""
            },
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=10,
            verify=self.ca,
            cert=self.cert
        )
        assert response.status_code == 200
        resp_body = response.json()
        assert resp_body["success"] == True
        assert resp_body["message"] == "Resource was successfully allocated"
        assert resp_body["data"]["resource"] == "nvidia geforce rtx 4050 laptop gpu"
        TestAPI.uuid = resp_body["data"]["uuid_key"]
        print(resp_body["data"])

    @allure.testcase("TC-11-2: Test allocation miner status")
    @pytest.mark.depends(on=["test_service_allocate_hotkey"])
    def test_service_check_miner_status(self):
        """
        Test /service/check_miner_status
        """
        response = httpx.post(
            url=self.url + "/service/check_miner_status",
            json=[self.hotkey, "test_miner"],
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=10,
            verify=self.ca,
            cert=self.cert
        )
        assert response.status_code == 200
        resp_body = response.json()
        assert resp_body["success"] == True
        assert resp_body["message"] == "List hotkey status successfully."
        assert len(resp_body["data"]) > 0
        assert resp_body["data"][0]["hotkey"] == self.hotkey
        assert resp_body["data"][0]["status"] == "Docker ONLINE"
        assert resp_body["data"][1]["hotkey"] == "test_miner"
        assert resp_body["data"][1]["status"] == "Not Found"
        print(resp_body["data"])

    @allure.testcase("TC-11-3: Test docker restart endpoint")
    @pytest.mark.depends(on=["test_service_allocate_hotkey"])
    def test_service_restart_docker(self):
        """
        Test /service/restart_docker
        """
        response = httpx.post(
            url=self.url + "/service/restart_docker?hotkey=" + self.hotkey + "&uuid_key=" + TestAPI.uuid,
            timeout=15,
            verify=self.ca,
            cert=self.cert
        )
        assert response.status_code == 200
        resp_body = response.json()
        assert resp_body["success"] == True
        assert resp_body["message"] == "Resource restarted successfully."
        print(resp_body)

    @allure.testcase("TC-11-4: Test docker exchange key endpoint")
    @pytest.mark.depends(on=["test_service_allocate_hotkey"])
    def test_service_exchange_key_docker(self):
        """
        Test /service/exchange_docker_key
        """
        response = httpx.post(
            url=self.url + "/service/exchange_docker_key?hotkey=" + self.hotkey +
                "&uuid_key=" + TestAPI.uuid + "&ssh_key=test_key",
            timeout=15,
            verify=self.ca,
            cert=self.cert
        )
        assert response.status_code == 200
        resp_body = response.json()
        assert resp_body["success"] == True
        assert resp_body["message"] == "Resource ssh_key is exchanged successfully."
        print(resp_body)

    @allure.testcase("TC-11-5: Test de-allocation hotkey endpoint")
    @pytest.mark.depends(on=["test_service_allocate_hotkey"])
    def test_service_deallocation_hotkey(self):
        """
        Test /service/deallocate
        """
        response = httpx.post(
            url=self.url + "/service/deallocate?hotkey=" + self.hotkey + "&uuid_key=" + TestAPI.uuid,
            timeout=15,
            verify=self.ca,
            cert=self.cert
        )
        assert response.status_code == 200
        resp_body = response.json()
        assert resp_body["success"] == True
        assert resp_body["message"] == "Resource deallocated successfully."
        print(resp_body)