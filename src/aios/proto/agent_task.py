
import datetime
import time

from anyio import Path


class AgentTodoResult:
    TODO_RESULT_CODE_OK = 0,
    TODO_RESULT_CODE_LLM_ERROR = 1,
    TODO_RESULT_CODE_EXEC_OP_ERROR = 2


    def __init__(self) -> None:
        self.result_code = AgentTodoResult.TODO_RESULT_CODE_OK
        self.result_str = None
        self.error_str = None
        self.op_list = None

    def to_dict(self) -> dict:
        result = {}
        result["result_code"] = self.result_code
        result["result_str"] = self.result_str
        result["error_str"] = self.error_str
        result["op_list"] = self.op_list
        return result




class AgentTodo:
    TODO_STATE_WAIT_ASSIGN = "wait_assign"
    TODO_STATE_INIT = "init"

    TODO_STATE_PENDING = "pending"
    TODO_STATE_WAITING_CHECK = "wait_check"
    TODO_STATE_EXEC_FAILED = "exec_failed"
    TDDO_STATE_CHECKFAILED = "check_failed"

    TODO_STATE_CASNCEL = "cancel"
    TODO_STATE_DONE = "done"
    TODO_STATE_EXPIRED = "expired"

    def __init__(self):
        self.todo_id = "todo#" + uuid.uuid4().hex
        self.title = None
        self.detail = None
        self.todo_path = None # get parent todo,sub todo by path
        #self.parent = None
        self.create_time = time.time()

        self.state = "wait_assign"
        self.worker = None
        self.checker = None
        self.createor = None

        self.need_check = True
        self.due_date = time.time() + 3600 * 24 * 2
        self.last_do_time = None
        self.last_check_time = None
        self.last_review_time = None

        self.depend_todo_ids = []
        self.sub_todos = {}

        self.result : AgentTodoResult = None
        self.last_check_result = None
        self.retry_count = 0
        self.raw_obj = None

    @classmethod
    def from_dict(cls,json_obj:dict) -> 'AgentTodo':
        todo = AgentTodo()
        if json_obj.get("id") is not None:
            todo.todo_id = json_obj.get("id")

        todo.title = json_obj.get("title")
        todo.state = json_obj.get("state")
        create_time = json_obj.get("create_time")
        if create_time:
            todo.create_time = datetime.fromisoformat(create_time).timestamp()

        todo.detail = json_obj.get("detail")
        due_date = json_obj.get("due_date")
        if due_date:
            todo.due_date = datetime.fromisoformat(due_date).timestamp()

        last_do_time = json_obj.get("last_do_time")
        if last_do_time:
            todo.last_do_time = datetime.fromisoformat(last_do_time).timestamp()
        last_check_time = json_obj.get("last_check_time")
        if last_check_time:
            todo.last_check_time = datetime.fromisoformat(last_check_time).timestamp()
        last_review_time = json_obj.get("last_review_time")
        if last_review_time:
            todo.last_review_time = datetime.fromisoformat(last_review_time).timestamp()

        todo.depend_todo_ids = json_obj.get("depend_todo_ids")
        todo.need_check = json_obj.get("need_check")
        #todo.result = json_obj.get("result")
        #todo.last_check_result = json_obj.get("last_check_result")
        todo.worker = json_obj.get("worker")
        todo.checker = json_obj.get("checker")
        todo.createor = json_obj.get("createor")
        if json_obj.get("retry_count"):
            todo.retry_count = json_obj.get("retry_count")

        todo.raw_obj = json_obj

        return todo

    def to_dict(self) -> dict:
        if self.raw_obj:
            result = self.raw_obj
        else:
            result = {}

        result["id"] = self.todo_id
        #result["parent_id"] = self.parent_id
        result["title"] = self.title
        result["state"] = self.state
        result["create_time"] = datetime.fromtimestamp(self.create_time).isoformat()
        result["detail"] = self.detail
        result["due_date"] = datetime.fromtimestamp(self.due_date).isoformat()
        result["last_do_time"] = datetime.fromtimestamp(self.last_do_time).isoformat() if self.last_do_time else None
        result["last_check_time"] = datetime.fromtimestamp(self.last_check_time).isoformat() if self.last_check_time else None
        result["last_review_time"] = datetime.fromtimestamp(self.last_review_time).isoformat() if self.last_review_time else None
        result["depend_todo_ids"] = self.depend_todo_ids
        result["need_check"] = self.need_check
        result["worker"] = self.worker
        result["checker"] = self.checker
        result["createor"] = self.createor
        result["retry_count"] = self.retry_count

        return result

    def can_check(self)->bool:
        if self.state != AgentTodo.TODO_STATE_WAITING_CHECK:
            return False

        now = datetime.now().timestamp()
        if self.last_check_time:
            time_diff = now - self.last_check_time
            if time_diff < 60*15:
                logger.info(f"todo {self.title} is already checked, ignore")
                return False

        return True

    def can_do(self) -> bool:
        match self.state:
            case AgentTodo.TODO_STATE_DONE:
                logger.info(f"todo {self.title} is done, ignore")
                return False
            case AgentTodo.TODO_STATE_CASNCEL:
                logger.info(f"todo {self.title} is cancel, ignore")
                return False
            case AgentTodo.TODO_STATE_EXPIRED:
                logger.info(f"todo {self.title} is expired, ignore")
                return False
            case AgentTodo.TODO_STATE_EXEC_FAILED:
                if self.retry_count > 3:
                    logger.info(f"todo {self.title} retry count ({self.retry_count}) is too many, ignore")
                    return False

        now = datetime.now().timestamp()
        time_diff = self.due_date - now
        if time_diff < 0:
            logger.info(f"todo {self.title} is expired, ignore")
            self.state = AgentTodo.TODO_STATE_EXPIRED
            return False

        if time_diff > 7*24*3600:
            logger.info(f"todo {self.title} is far before due date, ignore")
            return False

        if self.last_do_time:
            time_diff = now - self.last_do_time
            if time_diff < 60*15:
                logger.info(f"todo {self.title} is already do ignore")
                return False

        logger.info(f"todo {self.title} can do.")
        return True

class AgentTask:
    def __init__(self) -> None:
        self.task_id : str = "task#" + uuid.uuid4().hex
        self.task_path : Path = None # get parent todo,sub todo by path
        self.title = None
        self.detail = None
       
        self.create_time = time.time()

        self.state = "wait_assign"
        self.worker = None
        self.createor = None

        self.due_date = time.time() + 3600 * 24 * 2
        self.depend_task_ids = []
        self.step_todos = {}

        self.last_plan_time = None
        self.last_check_time = None
        #self.last_review_time = None

        self.result : LLMResult = None
        self.last_check_result = None
        self.retry_count = 0
        self.raw_obj = None



class AgentWorkLog:
    def __init__(self) -> None:
        pass


class AgentReport:
    def __init__(self) -> None:
        pass