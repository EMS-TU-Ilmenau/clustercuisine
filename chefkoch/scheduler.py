# import chefkoch
import threading


class Worker:
    def __init__(self, resultitem):
        # self.scheduler = scheduler
        self.resultitem = resultitem
        # if self.resultitem.dependencies.data
        # self.status = "ready"

    def execute(self):
        self.resultitem.execute


class Scheduler:
    """
    Responsible for scheduling the single jobs to fulfill
    th plan.
    """

    def __init__(self, plan):
        self.__update("initializing")
        self.plan = plan
        self.plan.completeJoblist()
        self.joblist = self.plan.joblist   # self.plan.joblist
        self.prepareWorkers()
        self.status = "ready"

        # self.__update("working")
        # pass

    def prepareWorkers(self):
        self.__update("preparing Workers")
        for priority in self.joblist:
            # self.joblist.append()
            for job in priority:
                # self.joblist.append(threading.Thread(target=Worker(job[1])))
                job.append(threading.Thread(target=Worker(job[1])))
        # self.__update("ready")
        pass

    def doWork(self):
        self.__update("working")


    def __update(self, toAssign):
        """
        update current status of scheduler
        """
        self.status = toAssign
