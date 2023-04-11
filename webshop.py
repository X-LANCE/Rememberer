#!/usr/bin/python3

import sys
sys.path.append("../WebShop")

import gym
import importlib
importlib.import_module("web_agent_site.envs")
#import web_agent_site.envs
from web_agent_site.utils import DEFAULT_FILE_PATH

import functools
from sentence_transformers import SentenceTransformer
import history
import yaml

import string
import webshop_agent
import agent_protos

import logging
import argparse
import datetime
import os

from typing import List, Dict
import numpy as np

#  Interfaces of WebAgentTextEnv {{{ # 
# def init( observation_mode: str = "html" # "html": raw html
#                                          # "text": " [SEP] " joined element text contents
#                                          # "text_rich": "\n" joined discription with bounded text contents
#                                          #              bounding labels are
#                                          #              [button][button_] and [clicked
#                                          #              button][clicked button_];
#                                          #              non-product-link as [clicked
#                                          #              button] will be prefixed with a
#                                          #              discription as "You have clicked {t}.\n"
#                                          # "url": url
#     , file_path: str = utils.DEFAULT_FILE_PATH # path to a json as the data file
#     , num_products: Optional[int]
#     , num_prev_actions: int = 0 # the number of history actions to append
#                                 # after the observation; actions are appended
#                                 # in a reverse order
#     , num_prev_obs: int = 0 # the number of history observations to append
#                             # after the current observation; observations are
#                             # appended in a reverse order; observations are
#                             # suffixed interleavingly with the actions like:
#                             # 
#                             # <current_obs> [SEP] act_{n-1} [SEP] obs_{n-1} [SEP] ... [SEP] obs_0
#     )
# 
# def step( action: str # search[keywords]
#                       # click[element], element should in
#                       # self.text_to_clickable and shouldn't be search
#         ) -> Tuple[ str # observation
#                   , float # reward
#                   , bool # done or not
#                   , None
#                   ]
# 
# def get_available_actions()\
#         -> Dict[str, bool | List[str]]
#         # {
#         #   "has_search_bar": bool
#         #   "clickables": List[str]
#         # }
# def get_instruction_text() -> str
# def observation -> str
# def state -> Dict[str, str]
#           # {
#           #     "url": str
#           #     "html": str
#           #     "instruction_text": str
#           # }
# text_to_clickable: Dict[str, Any] # {element_text: bs4 element}
# instruction_text: str
# 
# def reset( session: Optional[Union[int, str]] # int for the goal index
#          ) -> Tuple[ str # observation
#                    , None
#                    ]
#  }}} Interfaces of WebAgentTextEnv # 

def main():
    #  Command Line Options {{{ # 
    parser = argparse.ArgumentParser()

    parser.add_argument("--log-dir", default="logs", type=str)
    parser.add_argument("--config", default="openaiconfig.yaml", type=str)

    parser.add_argument( "--observation-mode"
                       , default="text", type=str
                       , choices=[ "html"
                                 , "text"
                                 , "text_rich"
                                 , "url"
                                 ]
                       )
    parser.add_argument("--file-path", type=str)
    parser.add_argument("--prev-actions", default=0, type=int)
    parser.add_argument("--prev-observations", default=0, type=int)

    # Matcher Options
    parser.add_argument( "--sentence-transformer"
                       , default="all-MiniLM-L12-v2", type=str
                       , choices=[ "all-MiniLM-L12-v2"
                                 , "all-mpnet-base-v2"
                                 ]
                       )

    # Replay Options
    parser.add_argument("--load-replay", type=str)
    parser.add_argument("--save-replay", type=str)
    parser.add_argument("--item-capacity", type=int)
    parser.add_argument("--action-capacity", type=int)
    parser.add_argument("--matcher", default="lcs", type=str, choices=["pgpat+iprel"])
    parser.add_argument("--gamma", default=1., type=float)
    parser.add_argument("--step-penalty", default=0., type=float)
    parser.add_argument("--update-mode", default="mean", type=str, choices=["mean", "const"])
    parser.add_argument("--learning-rate", default=0.1, type=float)
    parser.add_argument("--n-step-flatten", default=1, type=int)

    # Agent Options
    parser.add_argument("--prompt-template", type=str)
    parser.add_argument("--max-tokens", default=20, type=int)
    parser.add_argument("--temperature", default=0.1, type=float)
    parser.add_argument("--stop", type=str)
    parser.add_argument("--request-timeout", default=3., type=float)
    parser.add_argument("--manual", action="store_true")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--speech", action="store_true")

    args: argparse.Namespace = parser.parse_args()
    #  }}} Command Line Options # 

    #  Config Logger {{{ # 
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    datetime_str: str = datetime.datetime.now().strftime("%Y%m%d@%H%M%S")

    file_handler = logging.FileHandler(os.path.join(args.log_dir, "normal-{:}.log".format(datetime_str)))
    debug_handler = logging.FileHandler(os.path.join(args.log_dir, "debug-{:}.log".format(datetime_str)))
    stdout_handler = logging.StreamHandler(sys.stdout)
    sdebug_handler = logging.FileHandler(os.path.join(args.log_dir, "sdebug-{:}.log".format(datetime_str)))
    odebug_handler = logging.FileHandler(os.path.join(args.log_dir, "openai-{:}.log".format(datetime_str)))

    file_handler.setLevel(logging.INFO)
    debug_handler.setLevel(logging.DEBUG)
    stdout_handler.setLevel(logging.INFO)
    sdebug_handler.setLevel(logging.DEBUG)
    odebug_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(fmt="\x1b[1;33m[%(asctime)s \x1b[31m%(levelname)s \x1b[32m%(module)s/%(lineno)d-%(processName)s\x1b[1;33m] \x1b[0m%(message)s")
    file_handler.setFormatter(formatter)
    debug_handler.setFormatter(formatter)
    stdout_handler.setFormatter(formatter)
    sdebug_handler.setFormatter(formatter)
    odebug_handler.setFormatter(formatter)

    stdout_handler.addFilter(logging.Filter("webshop"))
    sdebug_handler.addFilter(logging.Filter("webshop"))
    odebug_handler.addFilter(logging.Filter("openaiE"))

    logger.addHandler(file_handler)
    logger.addHandler(debug_handler)
    logger.addHandler(stdout_handler)
    logger.addHandler(sdebug_handler)
    logger.addHandler(odebug_handler)

    logger = logging.getLogger("webshop")
    #  }}} Config Logger # 

    #  Build Agent and Environment {{{ # 
    sentence_transformer = SentenceTransformer(args.sentence_transformer)
    matcher_functions: Dict[str, history.LambdaMatcherConstructor[webshop_agent.Key]]\
            = { "pgpat+iprel": history.LambdaMatcherConstructor( [ history.PagePatMatcher
                                                                 , functools.partial( history.InsPageRelMatcher
                                                                                    , transformer=sentence_transformer
                                                                                    )
                                                                 ]
                                                               , [0.5, 0.5]
                                                               ).get_lambda_matcher
              }
    history_replay: history.HistoryReplay[webshop_agent.Key, webshop_agent.Action]\
            = history.HistoryReplay( args.item_capacity
                                   , args.action_capacity
                                   , matcher=matcher_functions[args.matcher]
                                   , gamma=args.gamma
                                   , step_penalty=args.step_penalty
                                   , update_mode=args.update_mode
                                   , learning_rate=args.learning_rate
                                   , n_step_flatten=args.n_step_flatten
                                   )
    history_replay.load_yaml(args.load_replay)

    with open(os.path.join(args.prompt_template, "prompt_pthw.txt")) as f:
        prompt_template = string.Template(f.read())
    with open(os.path.join(args.prompt_template, "input_template_w.txt")) as f:
        input_template = string.Template(f.read())
    with open(os.path.join(args.prompt_template, "advice_template.txt")) as f:
        advice_template = string.Template(f.read())
    template_group = agent_protos.TemplateGroup( whole_template=prompt_template
                                               , input_template=input_template
                                               , advice_template=advice_template
                                               )

    with open(args.config) as f:
        openaiconfig: Dict[str, str] = yaml.load(f, Loader=yaml.Loader)
    if args.speech:
        api_key: str = openaiconfig["spc_token"]
    else:
        api_key: str = openaiconfig["api_key"]
    model = webshop_agent.AutoAgent( history_replay=history_replay
                                   , prompt_templates=template_group
                                   , api_key=api_key
                                   , max_tokens=args.max_tokens
                                   , temperature=args.temperature
                                   , stop=args.stop
                                   , request_timeout=args.request_timeout
                                   , manual=args.manual
                                   , train=args.train
                                   , with_speech=args.speech
                                   , env_mode=args.observation_mode
                                   )
    #model = webshop_agent.ManualAgent(args.observation_mode)

    env = gym.make( "WebAgentTextEnv-v0"
                  , observation_mode=args.observation_mode
                  , file_path=(args.file_path if args.file_path is not None and args.file_path != ""
                                            else DEFAULT_FILE_PATH)
                  , num_products=None
                  , num_prev_actions=args.prev_actions
                  , num_prev_obs=args.prev_observations
                  )
    #  }}} Build Agent and Environment # 

    #  Workflow {{{ # 
    max_nb_tasks = 10
    max_nb_steps = 15
    max_task_id = 1000
    rng = np.random.default_rng()
    for i in range(max_nb_tasks):
        j: np.int64 = rng.integers(max_task_id)
        model.reset()
        task: str = env.get_instruction_text()
        observation: str = env.reset(session=int(j))[0]
        available_actions: List[str] = env.get_available_actions()["clickables"]

        nb_steps = 0
        nb_nothing_steps = 0

        reward = 0.
        total_reward = 0.
        succeeds = False
        while nb_steps<max_nb_steps:
            action: webshop_agent.Action = model( task
                                                , observation
                                                , reward
                                                , total_reward
                                                , available_actions
                                                )
            if action!="NOTHINGG":
                observation, reward, done, _ = env.step(action)
                total_reward += reward
                nb_steps += 1
                if done:
                    succeeds = True
                    break
            else:
                nb_nothing_steps += 1

        logger.info("\x1b[43mEND!\x1b[0m %s", task)
        logger.info( "\x1b[42mEND!\x1b[0m TaskIdx: %d, TaskId: %d, #Steps: %d(%d), Reward: %.1f, Succeds: %s"
                   , i, j, nb_steps, nb_nothing_steps, total_reward, str(succeeds)
                   )
    #  }}} Workflow # 

    if args.train:
        history_replay.save_yaml(args.save_replay)

if __name__ == "__main__":
    main()
