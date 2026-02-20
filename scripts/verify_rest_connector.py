
import asyncio
from connectors.base import get_connector, list_connectors
from connectors.rest_api.profiles.sophos import SophosProfile

async def verify():
    print(f"Registered connectors: {list_connectors()}")
    
    rest_connector_cls = get_connector("rest_api")
    if rest_connector_cls:
        print("SUCCESS: rest_api connector found in registry.")
    else:
        print("FAILURE: rest_api connector NOT found in registry.")
        return

    # Test Sophos XML generation
    sophos = SophosProfile()
    login_xml = sophos.get_login_xml("admin", "password123")
    wrapped = sophos.wrap_request(login_xml, "get", "SystemStatus")
    
    print("\nSophos XML Test:")
    print(wrapped.strip())
    
    if "<UserName>admin</UserName>" in wrapped and "<SystemStatus>" in wrapped:
        print("SUCCESS: Sophos XML generation looks correct.")
    else:
        print("FAILURE: Sophos XML generation is incorrect.")

if __name__ == "__main__":
    asyncio.run(verify())
