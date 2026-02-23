import win32serviceutil
import win32service
import win32event
import servicemanager
import sys
import logging
import asyncio
import os
from agents.windows_ad.service.ad_agent import ADAgent

# Ensure working directory is correct when running as service
os.chdir(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    filename='agent_service.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ADAgentService")

class AppServerSvc(win32serviceutil.ServiceFramework):
    _svc_name_ = "NetVaultADAgent"
    _svc_display_name_ = "NetVault Active Directory Agent"
    _svc_description_ = "Collects AD data and reports to NetVault Server."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.is_running = True

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.is_running = False

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.main()

    def main(self):
        try:
            agent = ADAgent()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            task = loop.create_task(agent.main_loop())
            
            # Periodically check for stop event
            while self.is_running:
                loop.run_until_complete(asyncio.sleep(1))
                rc = win32event.WaitForSingleObject(self.hWaitStop, 1000)
                if rc == win32event.WAIT_OBJECT_0:
                    break
            
            task.cancel()
            try:
                loop.run_until_complete(task)
            except asyncio.CancelledError:
                pass
            loop.close()
        except Exception as e:
            logger.error(f"Service error: {str(e)}")

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(AppServerSvc)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(AppServerSvc)
