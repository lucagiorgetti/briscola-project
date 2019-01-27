import tensorflow as tf
import argparse
import numpy as np
import os
import random
import shutil


## our stuff import
import graphic_visualizations as gv
import environment as brisc
from evaluate import evaluate

from agents.random_agent import RandomAgent
from agents.q_agent import QAgent
from agents.ai_agent import AIAgent
from utils import BriscolaLogger
from utils import CardsEncoding, CardsOrder, NetworkTypes, PlayerState



class CopyAgent(QAgent):
    '''Copied agent. Identical to a QAgent, but does not update itself'''
    def __init__(self, agent):

        # create a default QAgent
        super().__init__()

        # make the CopyAgent always greedy
        self.epsilon = 1.0

        # TODO: find a better way for copying the agent without saving the model
        # initialize the CopyAgent with the same weights as the passed QAgent
        if type(agent) is not QAgent:
            raise TypeError("CopyAgent __init__ requires argument of type QAgent")

        # create a temp directory where to save agent current model
        if not os.path.isdir('__tmp_model_dir__'):
            os.makedirs('__tmp_model_dir__')

        agent.save_model('__tmp_model_dir__')
        super().load_model('__tmp_model_dir__')

        # remove the temp directory after loading the model into the CopyAgent
        shutil.rmtree('__tmp_model_dir__')


    def update(self, *args):
        pass



def self_train(game, agent, num_epochs, evaluate_every, num_evaluations, model_dir = "", evaluation_dir = "evaluation_dir"):

    # initialize the list of old agents with a copy of the non trained agent
    old_agents = [CopyAgent(agent)]

    # Training starts
    best_total_wins = -1
    for epoch in range(1, num_epochs + 1):
        gv.printProgressBar(epoch, num_epochs,
                            prefix = f'Epoch: {epoch}',
                            length= 50)

        # picking an agent from the past as adversary
        agents = [agent, random.choice(old_agents)]

        # Play a briscola game to train the agent
        brisc.play_episode(game, agents)

        # Evaluation step
        if epoch % evaluate_every == 0:

            # Evaluation visualization directory
            if not os.path.isdir(evaluation_dir):
                os.mkdir(evaluation_dir)

            for ag in agents:
                ag.make_greedy()

            # Evaluation against old copy agent
            winners, points = evaluate(game, agents, num_evaluations)
            victory_rates_hist.append(winners)
            average_points_hist.append(points)

            output_path = evaluation_dir + "/fig_" + str(epoch)
            std_cur = gv.eval_visua_for_self_play(average_points_hist,
                             FLAGS,
                             victory_rates_hist,
                             output_path=output_path)
            # Storing std
            std_hist.append(std_cur)

            # Evaluation against random agent
            winners, points = evaluate(game, [agent, RandomAgent()], FLAGS.num_evaluations)
            output_prefix = evaluation_dir + '/againstRandom_' + str(epoch)
            gv.stats_plotter([agent, RandomAgent()], points, winners, output_prefix=output_prefix)

            # Saving the model if the agent performs better against random agent
            if winners[0] > best_total_wins:
                best_total_wins = winners[0]
                agent.save_model(model_dir)

            for ag in agents:
                ag.restore_epsilon()

            # After the evaluation we add the agent to the old agents
            old_agents.append(CopyAgent(agent))

            # Eliminating the oldest agent if maximum number of agents
            if len(old_agents) > FLAGS.max_old_agents:
                old_agents.pop(0)

    return best_total_wins



def main(argv=None):

    global victory_rates_hist
    victory_rates_hist  = []
    global average_points_hist
    average_points_hist = []
    global std_hist
    std_hist = []

    global victory_rates_hist_against_Random
    victory_rates_hist_against_Random  = []
    global average_points_hist_against_Random
    average_points_hist_against_Random = []
    global std_hist_against_Random
    std_hist_against_Random = []

    # Initializing the environment
    logger = BriscolaLogger(BriscolaLogger.LoggerLevels.TRAIN)
    game = brisc.BriscolaGame(2, logger)

    # Initialize agent
    agent = QAgent(
        FLAGS.epsilon, FLAGS.epsilon_increment, FLAGS.epsilon_max, FLAGS.discount,
        FLAGS.learning_rate)

    # Training
    best_total_wins = self_train(game, agent,
                                    FLAGS.num_epochs,
                                    FLAGS.evaluate_every,
                                    FLAGS.num_evaluations,
                                    FLAGS.model_dir,
                                    FLAGS.evaluation_dir)
    print('Best winning ratio : {:.2%}'.format(best_total_wins/FLAGS.num_evaluations))
    # Summary graph
    gv.summ_vis_self_play(victory_rates_hist, std_hist, FLAGS)



if __name__ == '__main__':

    # Parameters
    # ==================================================

    parser = argparse.ArgumentParser()

    # Training parameters
    parser.add_argument("--model_dir", default="saved_model", help="Where to save the trained model, checkpoints and stats", type=str)
    parser.add_argument("--num_epochs", default=100000, help="Number of training games played", type=int)
    parser.add_argument("--max_old_agents", default=50, help="Maximum number of old copies of QAgent stored", type=int)

    # Evaluation parameters
    parser.add_argument("--evaluate_every", default=1000, help="Evaluate model after this many epochs", type=int)
    parser.add_argument("--num_evaluations", default=500, help="Number of evaluation games against each type of opponent for each test", type=int)

    # State parameters
    parser.add_argument("--cards_order", default=CardsOrder.APPEND, choices=[CardsOrder.APPEND, CardsOrder.REPLACE, CardsOrder.VALUE], help="Where a drawn card is put in the hand")
    parser.add_argument("--cards_encoding", default=CardsEncoding.HOT_ON_NUM_SEED, choices=[CardsEncoding.HOT_ON_DECK, CardsEncoding.HOT_ON_NUM_SEED], help="How to encode cards")
    parser.add_argument("--player_state", default=PlayerState.HAND_PLAYED_BRISCOLA, choices=[PlayerState.HAND_PLAYED_BRISCOLA, PlayerState.HAND_PLAYED_BRISCOLASEED, PlayerState.HAND_PLAYED_BRISCOLA_HISTORY], help="Which cards to encode in the player state")

    # Reinforcement Learning parameters
    parser.add_argument("--epsilon", default=0, help="How likely is the agent to choose the best reward action over a random one", type=float)
    parser.add_argument("--epsilon_increment", default=5e-5, help="How much epsilon is increased after each action taken up to epsilon_max", type=float)
    parser.add_argument("--epsilon_max", default=0.85, help="The maximum value for the incremented epsilon", type=float)
    parser.add_argument("--discount", default=0.85, help="How much a reward is discounted after each step", type=float)

    # Network parameters
    parser.add_argument("--network", default=NetworkTypes.DRQN, choices=[NetworkTypes.DQN, NetworkTypes.DRQN], help="Neural Network used for approximating value function")
    parser.add_argument('--layers', default=[256, 128], help="Definition of layers for the chosen network", type=int, nargs='+')
    parser.add_argument("--learning_rate", default=1e-4, help="Learning rate for the network updates", type=float)
    parser.add_argument("--replace_target_iter", default=2000, help="Number of update steps before copying evaluation weights into target network", type=int)
    parser.add_argument("--batch_size", default=100, help="Training batch size", type=int)


    FLAGS = parser.parse_args()

    tf.app.run()