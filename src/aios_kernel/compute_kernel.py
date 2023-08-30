from abc import ABC, abstractmethod
from typing import Optional
import logging
import asyncio
from asyncio import Queue

from .agent import AgentPrompt
from .compute_node import ComputeNode
from .compute_task import ComputeTask,ComputeTaskState,ComputeTaskResult

logger = logging.getLogger(__name__)

# How to dispatch different computing tasks (some tasks may contain a large amount of state for correct execution)
# to suitable computing nodes, achieving a balance of speed, cost, and power consumption, 
# is the CORE GOAL of the entire computing task schedule system (aios_kernel).
class ComputeKernel:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.is_start = False

        return cls._instance

    def __init__(self) -> None:
        if self.is_start is True:
            return
        
        self.is_start = True
        self.task_queue = Queue()
        self.is_start = False
        self.compute_nodes = {}

        self.start()

    def run(self,task:ComputeTask) -> None:
        # check there is compute node can support this task
        if self.is_task_support(task) is False:
            logger.error(f"task {task.display()} is not support by any compute node")
            return
        # add task to working_queue
        self.task_queue.put_nowait(task)
        

    def start(self):
        if self.is_start is True:
            logger.warn("compute_kernel is already start")
            return
        
        self.is_start = True
        async def _run_task_loop():
            while True:
                logger.info("compute_kernel is waiting for task...")
                task = await self.task_queue.get()
                logger.info(f"compute_kernel get task: {task.display()}")
                c_node:ComputeNode = self._schedule(task)
                await c_node.push_task(task)
            
            logger.warn("compute_kernel is stoped!")
        
        asyncio.create_task(_run_task_loop())
        

    def _schedule(self,task) -> ComputeNode:
        for node in self.compute_nodes.values():
            if node.is_support(task) is True:
                return node
        logger.warning(f"task {task.display()} is not support by any compute node")
        return None

    def add_compute_node(self,node:ComputeNode):
        if self.compute_nodes.get(node.node_id) is not None:
            logger.warn(f"compute_node {node.display()} already in compute_kernel")
            return
        self.compute_nodes[node.node_id] = node
        logger.info(f"add compute_node {node.display()} to compute_kernel")

    def disable_compute_node(self,node_id:str):
        node = self.compute_nodes.get(node_id)
        if node is None:
            logger.warn(f"compute_node {node_id} not in compute_kernel")
            return
        node.enable = False

    def is_task_support(self,task:ComputeTask) -> bool:
        return True


    # friendly interface for use:
    def llm_completion(self,prompt:AgentPrompt,mode_name:Optional[str] = None,max_token:int = 0):
        # craete a llm_work_task ,push on queue's end
        # then task_schedule would run this task.(might schedule some work_task to another host)
        task_req = ComputeTask()
        task_req.set_llm_params(prompt,mode_name,max_token)
        self.run(task_req)
        return task_req

    async def do_llm_completion(self,prompt:AgentPrompt,mode_name:Optional[str] = None,max_token:int = 0) -> str:
        task_req = self.llm_completion(prompt,mode_name,max_token)
        async def check_timer():
            check_times = 0
            while True:
                if task_req.state == ComputeTaskState.DONE:
                    break

                if task_req.state == ComputeTaskState.ERROR:
                    break

                if check_times >=  20:
                    task_req.state = ComputeTaskState.ERROR
                    break

                await asyncio.sleep(0.5)
                check_times += 1
            
        await asyncio.create_task(check_timer())
        if task_req.state == ComputeTaskState.DONE:
            return task_req.result.result_str
              
        return "error!"
    