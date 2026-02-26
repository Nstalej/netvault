"""
NetVault - Windows AD Agent - Service Wrapper (DEPRECATED)

NOTE: This file is kept for backward compatibility but is NOT the 
recommended way to run the agent as a Windows service.

Use NSSM (Non-Sucking Service Manager) instead:
  nssm install NetVaultADAgent <python.exe path> <ad_agent.py path>
  nssm start NetVaultADAgent

The install.ps1 script handles NSSM installation automatically.
See: agents/windows_ad/installer/install.ps1
"""

import win32serviceutil
import win32service
import win32event
import servicemanager
import sys
import logging
import asyncio
import os
from ad_agent import ADAgent

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
            
            async def run_with_stop():
                """Run agent loop until stop event is set"""
                task = asyncio.create_task(agent.main_loop())
                # Check stop event periodically
                while self.is_running:
                    done, _ = await asyncio.wait({task}, timeout=1.0)
                    if done:
                        break  # main_loop finished (error or clean exit)
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            loop.run_until_complete(run_with_stop())
            loop.close()
        except Exception as e:
            logger.error(f"Service error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(AppServerSvc)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(AppServerSvc)
