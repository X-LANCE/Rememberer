<!-- vimc: call SyntaxRange#Include('```bib', '```', 'bib', 'NonText'): -->

# Rememberer: Large Language Models Are Semi-Parametric Reinforcement Learning Agents

Code repository for RLEM (Reinforcement Learning with Experience Memory) agent,
Rememberer. The corresponding paper is available at
[arXiv](https://arxiv.org/abs/2306.07929).  Our paper is accepted by NeurIPS
2023.

### Launch Test

`launchw.sh` is the launcher for the WebShop experiments. The corresponding
main program is `webshop.py`. To launch the experiment,
[WebShop](https://github.com/princeton-nlp/WebShop) environment should be set
up.

`launch.sh` is the launcher for the WikiHow experiments. The corresponding main
program is `wikihow.py`. To launch the program,
[Mobile-Env](https://github.com/X-LANCE/Mobile-Env) environment should be set
up. [WikiHow](https://huggingface.co/datasets/zdy023/WikiHow-taskset) task set
v1.2 is used. Additionally, a tokenizer is required for `VhIoWrapper` wrapper,
which can be downloaded from [Hugging Face](https://huggingface.co). The
tokenizer of `bert-base-uncased` is ok.

To launch test with static exemplars, you may add `--static` option in the
script.

To train a Rememberer agent, you may add `--train` option in the script. When
launching training, you may want to shrink the size of test set for the program
to prevent a complete evaluation each epoch.

The exemplars and prompt templates are stored under `prompts` and the initial
history memories are stored under `history-pools`.

OpenAI API key is configed through `openaiconfig.yaml`

### About Training Set

In this paper, two training sets are used for WebShop experiments:

1. S0: `[500, 510)`
2. S1: `[510, 520)`

These training sets are completely outside the test set of ReAct and this
paper.  You can simply use `--trainseta 0 --trainsetb 10` or `--trainseta 10
--trainsetb 20` to enable these two training sets. You can also try other
training sets.

The training sets for WikiHow experiments are selected from the complementary
set of the micro canonical set in the canonical set of WikiHow. They are

1. S0:
   + `add_a_contact_on_whatsapp-8`
   + `avoid_misgendering-0`
   + `become_a_grandmaster-7`
   + `become_a_hooters_girl-8`
   + `become_a_pro_footballP28soccerP29_manager-7`
   + `become_a_specialist_physician-4`
   + `be_cool_in_high_school_P28boysP29-0`
   + `care_for_florida_white_rabbits-4`
   + `fix_wet_suede_shoes-6`
   + `get_zorua_in_pokPC3PA9mon_white-6`
2. S1:
   + `be_free-0`
   + `build_a_robot_car-8`
   + `change_an_excel_sheet_from_read_only-4`
   + `choose_a_swiss_army_knife-8`
   + `color_streak_a_ponytail-0`
   + `come_up_with_a_movie_idea-4`
   + `contact_avast_customer_support-7`
   + `drink_mezcal-7`
   + `identify_hickory_nuts-6`
   + `wear_a_dress_to_school-6`

The selection simply keeps the balance of task categories and applies no other
filtering.

### Customized Codes for WebShop

As stated in the paper and the supplementary, the `text_rich` observation
format of WebShop is further simplified in the certain way of
[ReAct](https://github.com/ysymyth/ReAct). Besides, two typos of the closed tag
in the HTML templates are corrected. The customized codes ared provided at
[zdy023/WebShop](https://github.com/zdy023/WebShop).

### Citation

```bib
@article{DanyangZhang2023_Rememberer,
  author       = {Danyang Zhang and
                  Lu Chen and
                  Situo Zhang and
                  Hongshen Xu and
                  Zihan Zhao and
                  Kai Yu},
  title        = {Large Language Model Is Semi-Parametric Reinforcement Learning Agent},
  journal      = {CoRR},
  volume       = {abs/2306.07929},
  year         = {2023},
  url          = {https://doi.org/10.48550/arXiv.2306.07929},
  doi          = {10.48550/arXiv.2306.07929},
  eprinttype    = {arXiv},
  eprint       = {2306.07929},
}
```
