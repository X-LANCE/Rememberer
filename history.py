from typing import Dict, Tuple, Deque, List
from typing import Union, Optional, Callable, Sequence
import abc
#import dm_env

import numpy as np
import collections
import itertools
import yaml

import logging

logger = logging.getLogger("agent.history")
hlogger = logging.getLogger("history")

class Matcher(abc.ABC):
    #  class Matcher {{{ # 
    def __init__(self, query: "HistoryReplay.Key"):
        #  method __init__ {{{ # 
        self._query: HistoryReplay.Key = query
        #  }}} method __init__ # 

    def __call__(self, key: "HistoryReplay.Key") -> float:
        raise NotImplementedError
    #  }}} class Matcher # 

MatcherConstructor = Callable[["HistoryReplay.Key"], Matcher]

class LCSNodeMatcher(Matcher):
    #  class LCSNodeMatcher {{{ # 
    def __init__(self, query: "HistoryReplay.Key"):
        #  method __init__ {{{ # 
        super(LCSNodeMatcher, self).__init__(query)

        screen: str
        screen, _, _ = self._query
        self._node_sequence: List[str] = list( map( lambda n: n[1:n.index(" ")]
                                                  , screen.splitlines()
                                                  )
                                             )
        #  }}} method __init__ # 

    def __call__(self, key: "HistoryReplay.Key") -> float:
        #  method __call__ {{{ # 
        key_screen: str = key[0]
        key_node_sequence: List[str] = list( map( lambda n: n[1:n.index(" ")]
                                                , key_screen.splitlines()
                                                )
                                           )

        n: int = len(self._node_sequence)
        m: int = len(key_node_sequence)
        lcs_matrix: np.ndarray = np.zeros((n+1, m+1), dtype=np.int32)
        for i, j in itertools.product( range(1, n+1)
                                     , range(1, m+1)
                                     ):
            lcs_matrix[i, j] = lcs_matrix[i-1, j-1] + 1 if self._node_sequence[i-1]==key_node_sequence[j-1]\
                                                        else max( lcs_matrix[i-1, j]
                                                                , lcs_matrix[i, j-1]
                                                                )
        lcs: np.int32 = lcs_matrix[n, m]
        length: int = max(n, m)
        similarity: float = float(lcs)/length

        hlogger.debug("Req: %s", " ".join(self._node_sequence))
        hlogger.debug("Key: %s", " ".join(key_node_sequence))
        hlogger.debug( "LCS: %d, L1: %d, L2: %d, Sim: %.2f"
                    , lcs, n, m, similarity
                    )

        return similarity
        #  }}} method __call__ # 
    #  }}} class LCSNodeMatcher # 

class InsPatMatcher(Matcher):
    #  class InsPatMatcher {{{ # 
    _score_matrix: np.ndarray\
            = np.array( [ [1., .1, 0., 0., 0., 0.]
                        , [.1, 1., .3, .3, 0., 0.]
                        , [0., .3, 1., .8, .3, .3]
                        , [0., .3, .8, 1., .3, .3]
                        , [0., 0., .3, .3, 1., .8]
                        , [0., 0., .3, .3, .8, 1.]
                        ]
                      , dtype=np.float32
                      )

    def __init__(self, query: "HistoryReplay.Key"):
        #  method __init__ {{{ # 
        super(InsPatMatcher, self).__init__(query)

        instruction: str
        _, _, instruction = self._query

        self._pattern_id: int
        self._pattern_name: str
        self._pattern_id, self._pattern_name = InsPatMatcher._get_pattern(instruction)

        hlogger.debug( "Ins: %s, Pat: %d.%s"
                     , instruction
                     , self._pattern_id
                     , self._pattern_name
                     )
        #  }}} method __init__ # 

    def __call__(self, key: "HistoryReplay.Key") -> float:
        #  method __call__ {{{ # 
        if self._pattern_id==-1:
            return 0

        key_instruction: str = key[2]
        key_pattern_id: int
        key_pattern_name: str
        key_pattern_id, key_pattern_name = InsPatMatcher._get_pattern(key_instruction)

        hlogger.debug( "Key: %s, Pat: %d.%s"
                     , key_instruction
                     , key_pattern_id
                     , key_pattern_name
                     )

        if key_pattern_id==-1:
            return 0
        similarity: np.float32 = InsPatMatcher._score_matrix[ self._pattern_id
                                                            , key_pattern_id
                                                            ]

        hlogger.debug("Sim: %.2f", similarity)
        return float(similarity)
        #  }}} method __call__ # 

    @staticmethod
    def _get_pattern(instruction: str) -> Tuple[int, str]:
        #  method _get_pattern {{{ # 
        if instruction=="":
            return 0, "search"
        if instruction.startswith("Access the "):
            if instruction[11:].startswith("article"):
                return 1, "article"
            if instruction[11:].startswith("page of category"):
                return 3, "categ"
            if instruction[11:].startswith("about page"):
                return 5, "about"
        elif instruction.startswith("Check the "):
            if instruction[10:].startswith("author page"):
                return 2, "author"
            if instruction.startswith("reference list"):
                return 4, "reference"
        return -1, "unknown"
        #  }}} method _get_pattern # 
    #  }}} class InsPatMatcher # 

class LambdaMatcher(Matcher):
    #  class LambdaMatcher {{{ # 
    def __init__(self, matchers: List[Matcher], weights: Sequence[float]):
        self._matchers: List[Matcher] = matchers
        self._lambdas: np.ndarray = np.array(list(weights), dtype=np.float32)

    def __call__(self, key: "HistoryReplay.Key") -> float:
        scores: np.ndarray = np.asarray( list( map( lambda mch: mch(key)
                                                  , self._matchers
                                                  )
                                             )
                                       , dtype=np.float32
                                       )
        return float(np.sum(self._lambdas*scores))
    #  }}} class LambdaMatcher # 

class LambdaMatcherConstructor:
    #  class LambdaMatcherConstructor {{{ # 
    def __init__( self
                , matchers: List[MatcherConstructor]
                , weights: Sequence[float]
                ):
        self._matchers: List[MatcherConstructor] = matchers
        self._weights: Sequence[float] = weights

    def get_lambda_matcher(self, query):
        matchers: List[Matcher] = list( map( lambda mch: mch(query)
                                           , self._matchers
                                           )
                                      )
        return LambdaMatcher(matchers, self._weights)
    #  }}} class LambdaMatcherConstructor # 

class HistoryReplay:
    #  class HistoryReplay {{{ # 
    Key = Tuple[ str # screen representation
               , str # task description
               , str # step instruction
               ]
    Action = Tuple[str, str]
    InfoDict = Dict[ str
                   , Union[ float
                          , int
                          , List[Action]
                          ]
                   ]
    ActionDict = Dict[ Action
                     , Dict[ str
                           , Union[int, float]
                           ]
                     ]
    Record = Dict[str, Union[InfoDict, ActionDict]]

    def __init__( self
                , item_capacity: Optional[int]
                , action_capacity: Optional[int]
                , matcher: MatcherConstructor
                , gamma: float = 1.
                , step_penalty: float = 0.
                , update_mode: str = "mean"
                , learning_rate: float = 0.1
                , n_step_flatten: Optional[int] = 1
                , action_history_update_mode: str = "shortest"
                ):
        #  method __init__ {{{ # 
        """
        Args:
            item_capacity (Optional[int]): the optional item capacity limit of
              the history pool
            action_capacity (Optional[int]): the optional action capacity of
              each item in the history pool
            matcher (MatcherConstructor): matcher constructor

            gamma (float): the discount in calculation of the value function
            step_penalty (float): an optional penalty for the step counts

            update_mode (str): "mean" or "const"
            learning_rate (float): learning rate
            n_step_flatten (Optional[int]): flatten the calculation of the estimated q
              value up to `n_step_flatten` steps

            action_history_update_mode (str): "longest", "shortest", "newest",
              or "oldest"
        """

        self._record: Dict[ HistoryReplay.Key
                          , HistoryReplay.Record
                          ] = {}

        self._item_capacity: Optional[int] = item_capacity
        self._action_capacity: Optional[int] = action_capacity
        self._matcher: MatcherConstructor = matcher

        self._gamma: float = gamma
        if n_step_flatten is not None:
            self._multi_gamma: float = gamma ** n_step_flatten
            self._filter: np.ndarray = np.logspace( 0, n_step_flatten
                                                  , num=n_step_flatten
                                                  , endpoint=False
                                                  , base=self._gamma
                                                  )[::-1] # (n,)

        self._step_penalty: float = step_penalty

        self._update_mode: str = update_mode
        self._learning_rate: float = learning_rate
        self._n_step_flatten: Optional[int] = n_step_flatten

        self._action_history_update_mode: str = action_history_update_mode

        maxlenp1: Optional[int] = self._n_step_flatten+1 if self._n_step_flatten is not None else None
        self._action_buffer: Deque[Optional[HistoryReplay.Action]] = collections.deque(maxlen=self._n_step_flatten)
        self._action_history: List[HistoryReplay.Action] = []
        self._observation_buffer: Deque[HistoryReplay.Key]\
                = collections.deque(maxlen=maxlenp1)
        self._reward_buffer: Deque[float] = collections.deque(maxlen=maxlenp1)
        self._total_reward: float = 0.
        self._total_reward_buffer: Deque[float] = collections.deque(maxlen=maxlenp1)

        self._similarity_matrix: np.ndarray = np.zeros( (self._item_capacity, self._item_capacity)
                                                      , dtype=np.float32
                                                      )
        #self._index_pool: Deque[int] = collections.deque(range(self._item_capacity))
        #self._index_dict: Dict[HistoryReplay.Key, int] = {}
        self._keys: List[HistoryReplay] = []
        #  }}} method __init__ # 

    def __getitem__(self, request: Key) ->\
            List[ Tuple[ Key
                       , Record
                       , float
                       ]
                ]:
        #  method __getitem__ {{{ # 
        """
        Args:
            request (Key): the observation

        Returns:
            List[Tuple[Key, Record, float]]: the retrieved action-state value
              estimations sorted by matching scores
        """

        matcher: Matcher = self._matcher(request)
        match_scores: List[float] =\
                list( map( matcher
                         , self._record.keys()
                         )
                    )
        candidates: List[ Tuple[ HistoryReplay.Record
                               , float
                               ]
                        ] = list( sorted( zip( self._record.keys()
                                             , map(lambda k: self._record[k], self._record.keys())
                                             , match_scores
                                             )
                                        , key=(lambda itm: itm[2])
                                        , reverse=True
                                        )
                                )
        return candidates
        #  }}} method __getitem__ # 

    def update( self
              , step: Key, reward: float, action: Optional[Action]=None
              ):
        #  method update {{{ # 
        """
        Args:
            step (Key): the new state transitted to after `action` is performed
            reward (float): the reward corresponding to the new state
            action (Optional[Action]): the performed action, may be null if it is
              the initial state
        """

        self._action_buffer.append(action)
        if action is not None:
            self._action_history.append(action)
        self._observation_buffer.append(step)
        self._reward_buffer.append(reward)
        self._total_reward += reward
        self._total_reward_buffer.append(self._total_reward)
        if self._observation_buffer.maxlen is None\
                or len(self._observation_buffer)<self._observation_buffer.maxlen:
            return

        step = self._observation_buffer[0]
        action: HistoryReplay.Action = self._action_buffer[0]
        step_: HistoryReplay.Key = self._observation_buffer[-1]
        reward: float = self._reward_buffer[1]

        action_history: List[HistoryReplay.Action] = self._action_history[:-self._n_step_flatten]
        last_reward: float = self._reward_buffer[0]
        total_reward: float = self._total_reward_buffer[0]

        if not self._insert_key( step
                               , action_history
                               , last_reward
                               , total_reward
                               ):
            return

        new_estimation: np.float64 = np.convolve( np.asarray(self._reward_buffer, dtype=np.float32)[1:]
                                                , self._filter
                                                , mode="valid"
                                                )[0]

        action_dict: HistoryReplay.ActionDict = self._record[step]["action_dict"]
        self._update_action_record(action_dict, action, reward, float(new_estimation), step_)
        self._prune_action(action_dict)
        #  }}} method update # 

    def new_trajectory(self):
        #  method new_trajectory {{{ # 
        if len(self._action_buffer)<1\
                or len(self._action_buffer)==1 and self._action_buffer[0] is None:
            self._action_buffer.clear()
            self._action_history.clear()
            self._observation_buffer.clear()
            self._reward_buffer.clear()
            self._total_reward_buffer.clear()

            return

        if self._action_buffer[0] is None:
            self._action_buffer.popleft()
            #self._reward_buffer.popleft()

        rewards = np.asarray(self._reward_buffer, dtype=np.float32)[1:]
        if self._n_step_flatten is not None:
            convolved_rewards = np.convolve( rewards, self._filter
                                           , mode="full"
                                           )[self._n_step_flatten-1:]
        else:
            convolved_rewards = np.convolve( rewards
                                           , np.logspace( 0, len(rewards)
                                                        , num=len(rewards)
                                                        , endpoint=False
                                                        , base=self._gamma
                                                        )[::-1]
                                           , mode="full"
                                           )[len(rewards)-1:]

        end_point: Optional[int] = -len(self._action_buffer)

        for k, act, rwd, cvl_rwd\
                , e_p, l_rwd, ttl_rwd in zip( list(self._observation_buffer)[:-1]
                                            , self._action_buffer
                                            , self._reward_buffer
                                            , convolved_rewards
                                            , range(end_point, 0)
                                            , list(self._reward_buffer)[:-1]
                                            , list(self._total_reward_buffer)[:-1]
                                            ):
            action_history: List[HistoryReplay.Action] = self._action_history[:e_p]
            if not self._insert_key( k
                                   , action_history
                                   , l_rwd
                                   , ttl_rwd
                                   ):
                continue

            action_dict: HistoryReplay.ActionDict = self._record[k]["action_dict"]
            self._update_action_record(action_dict, act, float(rwd), float(cvl_rwd), None)
            self._prune_action(action_dict)

        self._action_buffer.clear()
        self._action_history.clear()
        self._observation_buffer.clear()
        self._reward_buffer.clear()
        self._total_reward_buffer.clear()
        #  }}} method new_trajectory # 

    def _insert_key( self, key: Key
                   , action_history: List[Action]
                   , last_reward: float
                   , total_reward: float
                   ) -> bool:
        #  method _insert_key {{{ # 

        logger.debug("Record: %d, Keys: %d", len(self._record), len(self._keys))

        if key not in self._record:
            #  Insertion Policy (Static Capacity Limie) {{{ # 
            matcher: Matcher = self._matcher(key)
            similarities: np.ndarray = np.asarray(list(map(matcher, self._keys)))

            if self._item_capacity is not None and self._item_capacity>0\
                    and len(self._record)==self._item_capacity:

                max_new_similarity_index: np.int64 = np.argmax(similarities)
                max_old_similarity_index: Tuple[ np.int64
                                               , np.int64
                                               ] = np.unravel_index( np.argmax(self._similarity_matrix)
                                                                   , self._similarity_matrix.shape
                                                                   )
                if similarities[max_new_similarity_index]>=self._similarity_matrix[max_old_similarity_index]:
                    # drop the new one
                    return False
                # drop an old one according to the number of action samples
                action_dict1: HistoryReplay.ActionDict = self._record[self._keys[max_old_similarity_index[0]]]
                nb_samples1: int = sum(map(lambda d: d["number"], action_dict1.values()))

                action_dict2: HistoryReplay.ActionDict = self._record[self._keys[max_old_similarity_index[1]]]
                nb_samples2: int = sum(map(lambda d: d["number"], action_dict2.values()))

                drop_index: np.int64 = max_old_similarity_index[0] if nb_samples1>=nb_samples2 else max_old_similarity_index[1]

                del self._record[self._keys[drop_index]]
                self._keys[drop_index] = key
                similarities[drop_index] = 0.
                self._similarity_matrix[drop_index, :] = similarities
                self._similarity_matrix[:, drop_index] = similarities
                self._record[key] = { "other_info": { "action_history": action_history
                                                    , "last_reward": last_reward
                                                    , "total_reward": total_reward
                                                    , "number": 1
                                                    }
                                    , "action_dict": {}
                                    }
            else:
                new_index: int = len(self._record)
                self._keys.append(key)
                self._similarity_matrix[new_index, :new_index] = similarities
                self._similarity_matrix[:new_index, new_index] = similarities
                self._record[key] = { "other_info": { "action_history": action_history
                                                    , "last_reward": last_reward
                                                    , "total_reward": total_reward
                                                    , "number": 1
                                                    }
                                    , "action_dict": {}
                                    }
            #  }}} Insertion Policy (Static Capacity Limie) # 
        else:
            other_info: HistoryReplay.InfoDict = self._record[key]["other_info"]

            if self._action_history_update_mode=="longest"\
                    and len(action_history) >= len(other_info["action_history"]):
                other_info["action_history"] = action_history
            elif self._action_history_update_mode=="shortest"\
                    and len(action_history) <= len(other_info["action_history"]):
                other_info["action_history"] = action_history
            elif self._action_history_update_mode=="newest":
                other_info["action_history"] = action_history
            elif self._action_history_update_mode=="oldest":
                pass

            number: int = other_info["number"]
            number_: int = number + 1
            other_info["number"] = number_

            if self._update_mode=="mean":
                other_info["last_reward"] = float(number)/number_ * other_info["last_reward"]\
                                          + 1./number_ * last_reward
                other_info["total_reward"] = float(number)/number_ * other_info["total_reward"]\
                                           + 1./number_ * total_reward
            elif self._update_mode=="const":
                other_info["last_reward"] += self._learning_rate * (last_reward-other_info["last_reward"])
                other_info["total_reward"] += self._learning_rate * (total_reward-other_info["total_reward"])
        return True
        #  }}} method _insert_key # 

    def _update_action_record( self
                             , action_dict: ActionDict
                             , action: Action
                             , reward: float
                             , new_estimation: float
                             , end_step: Optional[Key]
                             )\
            -> Dict[str, Union[int, float]]:
        #  method _update_action_record {{{ # 
        if action not in action_dict:
            action_dict[action] = { "reward": 0.
                                  , "qvalue": 0.
                                  , "number": 0
                                  }
        action_record = action_dict[action]

        number: int = action_record["number"]
        number_: int = number + 1
        action_record["number"] = number_

        #  New Estimation of Q Value {{{ # 
        if end_step is not None:
            if end_step in self._record:
                action_dict: HistoryReplay.ActionDict = self._record[end_step]["action_dict"]
            else:
                record: HistoryReplay.Record = self[end_step][0][1]
                action_dict: HistoryReplay.ActionDict = record["action_dict"]
            qvalue_: float = max(map(lambda act: act["qvalue"], action_dict.values()))
            qvalue_ *= self._multi_gamma
        else:
            qvalue_: float = 0.
        new_estimation = new_estimation + qvalue_
        #  }}} New Estimation of Q Value # 

        if self._update_mode=="mean":
            action_record["reward"] = float(number)/number_ * action_record["reward"]\
                                    + 1./number_ * reward

            action_record["qvalue"] = float(number)/number_ * action_record["qvalue"]\
                                    + 1./number_ * new_estimation
        elif self._update_mode=="const":
            action_record["reward"] += self._learning_rate * (reward-action_record["reward"])
            action_record["qvalue"] += self._learning_rate * (new_estimation-action_record["qvalue"])
        #  }}} method _update_action_record # 

    def _prune_action(self, action_dict: ActionDict):
        #  method _remove_action {{{ # 
        if self._action_capacity is not None and self._action_capacity>0\
                and len(action_dict)>self._action_capacity:
            worst_action: str = min( action_dict
                                   , key=(lambda act: action_dict[act]["reward"])
                                   )
            del action_dict[worst_action]
        #  }}} method _remove_action # 

    def __str__(self) -> str:
        return yaml.dump(self._record, Dumper=yaml.Dumper)
    def load_yaml(self, yaml_file: str):
        #  method load_yaml {{{ # 
        with open(yaml_file) as f:
            self._record = yaml.load(f, Loader=yaml.Loader)
            self._keys = list(self._record.keys())
        #  }}} method load_yaml # 
    def save_yaml(self, yaml_file: str):
        with open(yaml_file, "w") as f:
            yaml.dump(self._record, f, Dumper=yaml.Dumper)
    #  }}} class HistoryReplay # 
