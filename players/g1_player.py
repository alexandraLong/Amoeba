import os
import pickle
import numpy as np
import logging
from amoeba_state import AmoebaState
import math

from queue import PriorityQueue, Queue

class Player:
    def __init__(self, rng: np.random.Generator, logger: logging.Logger, metabolism: float, goal_size: int,
                 precomp_dir: str) -> None:
        """Initialise the player with the basic amoeba information

            Args:
                rng (np.random.Generator): numpy random number generator, use this for same player behavior across run
                logger (logging.Logger): logger use this like logger.info("message")
                metabolism (float): the percentage of amoeba cells, that can move
                goal_size (int): the size the amoeba must reach
                precomp_dir (str): Directory path to store/load pre-computation
        """

        # precomp_path = os.path.join(precomp_dir, "{}.pkl".format(map_path))

        # # precompute check
        # if os.path.isfile(precomp_path):
        #     # Getting back the objects:
        #     with open(precomp_path, "rb") as f:
        #         self.obj0, self.obj1, self.obj2 = pickle.load(f)
        # else:
        #     # Compute objects to store
        #     self.obj0, self.obj1, self.obj2 = _

        #     # Dump the objects
        #     with open(precomp_path, 'wb') as f:
        #         pickle.dump([self.obj0, self.obj1, self.obj2], f)

        self.rng = rng
        self.logger = logger
        self.metabolism = metabolism
        self.goal_size = goal_size
        self.current_size = goal_size / 4

        self.size_to_radius = {}
        for i in range(50,3,-1):
            self.size_to_radius[i] = i**2 - (i-3)**2

    def move(self, last_percept: AmoebaState, current_percept: AmoebaState, info: int) -> (list, list, int):
        """Function which retrieves the current state of the amoeba map and returns an amoeba movement

            Args:
                last_percept (AmoebaState): contains state information after the previous move
                current_percept(AmoebaState): contains current state information
                info (int): byte (ranging from 0 to 256) to convey information from previous turn
            Returns:
                Tuple[List[Tuple[int, int]], List[Tuple[int, int]], int]: This function returns three variables:
                    1. A list of cells on the periphery that the amoeba retracts
                    2. A list of positions the retracted cells have moved to
                    3. A byte of information (values range from 0 to 255) that the amoeba can use
        """
        #print(current_percept.amoeba_map)

        #store center as information. Center would be (info, info)
        #close cavities left of the center
            
        r = self.largest_radius_given_size(current_percept.current_size)

        if info == 0:
            info = r
        
        centers = []

        #new center is the max_x, max_y
        for i in range(140, 0, -1):
            i = i%100
            if current_percept.amoeba_map[i][i] == 1:
                if current_percept.amoeba_map[i][i-1] == 1 and current_percept.amoeba_map[i-1][i] == 1:
                    centers.append((i,i))

                #a new center or is currently being shrunk
                if len(centers) == 1:
                    if current_percept.amoeba_map[i][i+1] == 0 and current_percept.amoeba_map[i+1][i] == 0:
                        if current_percept.amoeba_map[i][i-1] == 1 and current_percept.amoeba_map[i-1][i] == 1:
                            info = r
        
        center = centers[0]

        #center = (53,53)
        next_center = ((center[0]+info)%100, (center[1]+info)%100)
        
        formation_needed = self.find_surround_cells(info, info, center)
        #check = self.formation_secured(current_percept.amoeba_map, formation_needed)

        movable = None
        retract = None

        #create and continue formation
        print("Formation at: ", center, next_center)

        #cells I can retract
        retract = self.furthest_to_top_right(list(set(current_percept.periphery).difference(set(formation_needed))), next_center, current_percept)

        #holes behind center
        cavity_cells = self.find_island(current_percept.amoeba_map, (center[0]-1, center[1]-1))
        shrink_cells = []

        for i in cavity_cells:
            if i in set(current_percept.movable_cells):
                shrink_cells.append(i)

        formation_moves = list(set(formation_needed).intersection(set(current_percept.movable_cells)))
        formation_moves.sort(key = lambda x : self.manhattan_distance(x, center))

        movable = list(shrink_cells) + formation_moves


        #print(retract)
        #print(movable)
            

        if len(retract) > len(movable):
            retract = retract[:len(movable)]
        elif len(retract) < len(movable):
            movable = movable[:len(retract)]

        if len(retract) > self.metabolism*current_percept.current_size:
            retract = retract[:int(self.metabolism*current_percept.current_size)]

        if len(movable) > self.metabolism*current_percept.current_size:
            movable = movable[:int(self.metabolism*current_percept.current_size)]

        #print(retract)
        #print(movable)

        return retract, movable, info

    """def mend_retract_movable(self, retract, movable, current_percept):
        ret_i = 0
        move_i = 0

        move = []
        ret = []

        while ret_i < len(retract) and move_i < len(movable):
            ret.append(retract[ret_i])

            while move_i < len(movable) and len(move) < len(ret):
                if self.check_move(ret, move + [movable[move_i]], current_percept):
                    move.append(movable[move_i])
                
                move_i += 1

        if len(ret) > len(move):
            ret = ret[:len(move)]
        elif len(ret) < len(move):
            move = move[:len(ret)]

        return ret, move"""
        
    def manhattan_distance(self, src, trgt):
        x1 = src[0]
        y1 = src[1]

        x2 = trgt[0]
        y2 = trgt[1]

        x_dist = min(x2-x1, 100+x1-x2)
        y_dist = min(y2-y1, 100+y1-y2)

        return x_dist**2 + y_dist**2

    def find_island(self, amoeba_map, start):

        if amoeba_map[start[0]][start[1]] == 1:
            return []

        seen = set()
        in_queue = set()
        l = []

        q = Queue()
        q.put(start)

        while q.qsize() > 0:
            curr = q.get()

            if q in seen:
                continue
            else:
                seen.add(curr)
                l.append(curr)
                for n in self.find_neighbor(curr, amoeba_map):
                    if n not in seen and n not in in_queue:
                        q.put(n)
                        in_queue.add(n)

        return l[::-1]

    def find_neighbor(self, curr, amoeba_map):
        x, y = curr
        out = []
        if amoeba_map[x][(y - 1) % 100] == 0:
            out.append((x, (y - 1) % 100))
        if amoeba_map[x][(y + 1) % 100] == 0:
            out.append((x, (y + 1) % 100))
        if amoeba_map[(x - 1) % 100][y] == 0:
            out.append(((x - 1) % 100, y))
        if amoeba_map[(x + 1) % 100][y] == 0:
            out.append(((x + 1) % 100, y))

        return out

    #return "count" points closest furthest from a certain point
    def furthest_to_top_right(self, retractable, target, current_percept):

        pq = PriorityQueue()

        for cell in retractable:
            pq.put((-self.manhattan_distance(cell, target), cell))

        retract = []
        for i in range(pq.qsize()):
            test = pq.get()[1]
            if self.check_move(retract+[test], current_percept):
                retract.append(test)

        return retract

    def find_movable_cells(self, periphery, amoeba_map, bacteria, mini):
        movable = []
        new_periphery = list(set(periphery))
        for i, j in new_periphery:
            nbr = self.find_movable_neighbor(i, j, amoeba_map, bacteria)
            for x, y in nbr:
                if (x, y) not in movable:
                    movable.append((x, y))

        #movable += retract

        return movable#[:mini]

    def find_movable_neighbor(self, x, y, amoeba_map, bacteria):
        out = []
        if (x, y) not in bacteria:
            if amoeba_map[x][(y - 1) % 100] == 0:
                out.append((x, (y - 1) % 100))
            if amoeba_map[x][(y + 1) % 100] == 0:
                out.append((x, (y + 1) % 100))
            if amoeba_map[(x - 1) % 100][y] == 0:
                out.append(((x - 1) % 100, y))
            if amoeba_map[(x + 1) % 100][y] == 0:
                out.append(((x + 1) % 100, y))

        return out

    #for a given amoeba size, and a required thickness, return the cells needed to be occupied 
    #uses center as a reference point
    def find_surround_cells(self, radius, end_length, center):
        
        #2-Width L
        cells = set()

        center_x, center_y = center

        for i in range(int(radius)+1):
            cells.add((center_x+i, center_y))
            cells.add((center_x, center_y+i))

        for i in range(int(radius)+1):
            cells.add((center_x+i, center_y-1))
            cells.add((center_x-1, center_y+i))

        for i in range(-1, end_length+1):
            cells.add((center_x+radius, center_y+i))
            cells.add((center_x+i, center_y+radius))

        fixed_cells = set()
        for x,y in cells:
            fixed_cells.add((x%100, y%100))

        return fixed_cells

    def largest_radius_given_size(self, size):
        
        for radius, cell_count in self.size_to_radius.items():
            if cell_count <= size:
                return radius-2


    def check_move(self, retract, current_precept):

        periphery = current_precept.periphery

        if not set(retract).issubset(set(periphery)):
            return False

        """movable = retract[:]
        new_periphery = list(set(periphery).difference(set(retract)))
        for i, j in new_periphery:
            nbr = self.find_movable_neighbor(i, j, current_precept.amoeba_map, current_precept.bacteria)
            for x, y in nbr:
                if (x, y) not in movable:
                    movable.append((x, y))"""

        amoeba = np.copy(current_precept.amoeba_map)
        amoeba[amoeba < 0] = 0
        amoeba[amoeba > 0] = 1

        for i, j in retract:
            amoeba[i][j] = 0

        tmp = np.where(amoeba == 1)
        result = list(zip(tmp[0], tmp[1]))
        check = np.zeros((100, 100), dtype=int)

        stack = result[0:1]
        while len(stack):
            a, b = stack.pop()
            check[a][b] = 1

            if (a, (b - 1) % 100) in result and check[a][(b - 1) % 100] == 0:
                stack.append((a, (b - 1) % 100))
            if (a, (b + 1) % 100) in result and check[a][(b + 1) % 100] == 0:
                stack.append((a, (b + 1) % 100))
            if ((a - 1) % 100, b) in result and check[(a - 1) % 100][b] == 0:
                stack.append(((a - 1) % 100, b))
            if ((a + 1) % 100, b) in result and check[(a + 1) % 100][b] == 0:
                stack.append(((a + 1) % 100, b))

        return (amoeba == check).all()