# -*- coding: UTF-8 -*-

from __future__ import print_function
import os

from tensorflow.python.ops.gen_parsing_ops import parse_single_example_eager_fallback
from tensorflow.python.ops.nn_ops import pool

print('*** Current working path ***')
print(os.getcwd())
# os.chdir(os.getcwd()+"/NeuRec")

from prefetch_generator import BackgroundGenerator, background, __doc__
import tensorflow as tf
import numpy as np
import os
import sys
import random
import collections
import heapq
import math
import logging
from time import time

from time import strftime, localtime
import multiprocessing
from scipy.special import softmax, expit
from tensorflow.python.ops.gen_batch_ops import batch
from model_api import BPRMF, ConditionalBPRMF, BPRMFTempPop
from batch_test import *
from matplotlib import pyplot as plt
import pandas as pd
import gc

import sys

sys.path.append(os.getcwd())
print(sys.path)
from evaluator import ProxyEvaluator
from util import Logger
import random as rd
import signal

from used_metric import get_performance

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'


def term(sig_num, addtion):
    print('term current pid is %s, group id is %s' % (os.getpid(), os.getpgrp()))
    os.killpg(os.getpgid(os.getpid()), signal.SIGKILL)


signal.signal(signal.SIGTERM, term)

cores = multiprocessing.cpu_count() // 2
max_pre = 1
print("half cores:", cores)


class Train_data_generator():
    def __init__(self) -> None:
        worker = min(cores // max_pre, 10)
        worker = max(2, worker)
        batch_size = data.batch_size
        tot_num = data.n_train
        tot_batch = tot_num // batch_size + 1
        self.tot_batch = tot_batch
        each_batch = tot_batch // worker + 1
        self.sub_sampel_batchs = [each_batch] * worker
        super().__init__()
        self.pool = multiprocessing.Pool(worker)
        self.Queue_buffer = multiprocessing.Manager().Queue(worker * 20)

    def generator(self):
        self.pool.map_async(self.generator_n_batch,
                            [(self.Queue_buffer, n_batch) for n_batch in self.sub_sampel_batchs])
        yield_num = 0
        while True:
            if yield_num == self.tot_batch:
                break
            try:
                one_batch = self.Queue_buffer.get()
                yield one_batch
                yield_num += 1
            except:
                pass

    def generator_n_batch(self, input_t_):
        '''
        sample n_batch without popularity
        '''
        Queue_buffer, n_batch = input_t_
        all_users = list(data.train_user_list.keys())
        batch_size = data.batch_size
        for i in range(n_batch):
            batch_pos = []
            batch_neg = []
            if batch_size <= data.n_users:
                batch_users = rd.sample(all_users, batch_size)
            else:
                batch_users = [rd.choice(all_users) for _ in range(batch_size)]

            for u in batch_users:
                u_clicked_items = data.train_user_list[u]
                if u_clicked_items == []:
                    batch_pos.append(0)
                else:
                    batch_pos.append(rd.choice(u_clicked_items))
                while True:
                    neg_item = rd.choice(data.items)
                    if neg_item not in u_clicked_items:
                        batch_neg.append(neg_item)
                        break
            one_batch = (batch_users, batch_pos, batch_neg)
            Queue_buffer.put(one_batch, True)  # put with blocked


def multi_generator():
    '''
    multi-processing Dataset Generator without popularity
    with pair-wise sampling
    '''
    worker = min(cores // max_pre, 10)
    worker = max(2, worker)
    pool = multiprocessing.Pool(worker)
    Queue_buffer = multiprocessing.Manager().Queue(worker * 20)
    batch_size = data.batch_size
    tot_num = data.n_train
    tot_batch = tot_num // batch_size + 1
    each_batch = tot_batch // worker + 1
    sub_sampel_batchs = [each_batch] * worker
    # for i in range(tot_batch):
    #     pool.apply_async(generator_one_batch,args=(Queue_buffer,))
    for n_batch in sub_sampel_batchs:
        pool.apply_async(generator_n_batch, args=(Queue_buffer, n_batch,))
    yield_num = 0
    while True:
        if yield_num == tot_batch:
            break
        try:
            one_batch = Queue_buffer.get()
            yield one_batch
            yield_num += 1
        except:
            pass
    pool.close()
    pool.join()


def multi_generator_finetune():
    '''
    multi-processing Dataset Generator with popularity  for Condition-based Model
    with pair-wise sampling
    '''
    worker = min(cores // max_pre, 10)
    worker = max(2, worker)
    pool = []
    Queue_buffer = multiprocessing.Queue(2000)
    Queue_info = multiprocessing.Manager().Queue(worker)
    batch_size = data.batch_size
    tot_num = data_fine_tune.n_train
    tot_batch = tot_num // batch_size + 1
    each_batch = tot_batch // worker + 1
    sub_sampel_batchs = [each_batch] * worker
    # for i in range(tot_batch):
    #     pool.apply_async(generator_one_batch,args=(Queue_buffer,))
    # pool.map_async(generator_n_batch_with_pop,[(Queue_buffer,n_batch) for n_batch in sub_sampel_batchs])
    for n_batch in sub_sampel_batchs:
        pool.append(
            multiprocessing.Process(target=generator_n_batch_finetune, args=(Queue_buffer, n_batch, Queue_info,)))
    for p in pool:
        p.start()
    for i in range(tot_batch):
        # print("... wait data....")
        yield Queue_buffer.get(True)
        # if i%1000 == 0:
        # print("runing..",i,tot_batch)
    # print("finish sampling....")
    for i in range(worker):
        Queue_info.put("out")
    for p in pool:
        p.join()
    print("sampled data finished")


def multi_generator_with_pop2():
    '''
    multi-processing Dataset Generator with popularity  for Condition-based Model
    with pair-wise sampling
    '''
    worker = min(cores // max_pre, 10)
    worker = max(2, worker)
    pool = []
    Queue_buffer = multiprocessing.Queue(2000)
    Queue_info = multiprocessing.Manager().Queue(worker)
    batch_size = data.batch_size
    tot_num = data.n_train
    tot_batch = tot_num // batch_size + 1
    each_batch = tot_batch // worker + 1
    sub_sampel_batchs = [each_batch] * worker
    if data.expo_popularity is None:  # temp_pop
        gen_n_batch_method = generator_n_batch_with_temp
    else:  # conditional MF
        mm_shape = len(data.expo_popularity.shape)
        if mm_shape > 1:  # s_condition
            gen_n_batch_method = generator_n_batch_with_pop
        elif mm_shape == 1:  # condition
            gen_n_batch_method = generator_n_batch_with_totpop
        else:
            raise NotImplementedError("maybe you should take generator without popularity!!!")
        # for i in range(tot_batch):
    #     pool.apply_async(generator_one_batch,args=(Queue_buffer,))
    # pool.map_async(generator_n_batch_with_pop,[(Queue_buffer,n_batch) for n_batch in sub_sampel_batchs])
    for n_batch in sub_sampel_batchs:
        pool.append(multiprocessing.Process(target=gen_n_batch_method, args=(Queue_buffer, n_batch, Queue_info,)))
    for p in pool:
        p.start()
    for i in range(tot_batch):
        # print("... wait data....")
        yield Queue_buffer.get(True)
        # if i%1000 == 0:
        # print("runing..",i,tot_batch)
    # print("finish sampling....")
    for i in range(worker):
        Queue_info.put("out")
    for p in pool:
        p.join()
    print("sampled data finished")


def multi_generator_with_pop():
    '''
    multi-processing Dataset Generator with popularity  for Condition-based Model
    with pair-wise sampling
    '''
    worker = min(cores // max_pre, 10)
    worker = max(2, worker)
    pool = multiprocessing.Pool(worker + 1)
    Queue_buffer = multiprocessing.Manager().Queue(worker * 20)
    batch_size = data.batch_size
    tot_num = data.n_train
    tot_batch = tot_num // batch_size + 1
    each_batch = tot_batch // worker + 1
    sub_sampel_batchs = [each_batch] * worker
    mm_shape = len(data.expo_popularity.shape)
    if mm_shape > 1:
        gen_n_batch_method = generator_n_batch_with_pop
    elif mm_shape == 1:
        gen_n_batch_method = generator_n_batch_with_totpop
    else:
        raise NotImplementedError("maybe you should take generator without popularity!!!")
    # for i in range(tot_batch):
    #     pool.apply_async(generator_one_batch,args=(Queue_buffer,))
    for n_batch in sub_sampel_batchs:
        pool.apply_async(gen_n_batch_method, args=(Queue_buffer, n_batch,))
    yield_num = 0
    while True:
        if yield_num == tot_batch:
            break
        try:
            one_batch = Queue_buffer.get()
            yield one_batch
            yield_num += 1
        except:
            pass
    pool.close()
    pool.join()


def generator_n_batch_finetune(Queue_buffer, n_batch, q_info):
    '''
    sample n_batch without popularity for fine_tune
    '''
    all_users = list(data_fine_tune.train_user_list.keys())
    batch_size = data_fine_tune.batch_size
    for i in range(n_batch):
        batch_pos = []
        batch_neg = []
        if batch_size <= data_fine_tune.n_users:
            batch_users = rd.sample(all_users, batch_size)
        else:
            batch_users = [rd.choice(all_users) for _ in range(batch_size)]
        for u in batch_users:
            u_clicked_items_tot = data.train_user_list[u]  # history clicked items
            u_clicked_items = data_fine_tune.train_user_list[u]  # fine_tune data
            if u_clicked_items == []:
                batch_pos.append(0)
            else:
                batch_pos.append(rd.choice(u_clicked_items))
            while True:
                neg_item = rd.choice(data.items)
                if neg_item not in u_clicked_items_tot:
                    batch_neg.append(neg_item)
                    break
        one_batch = (batch_users, batch_pos, batch_neg)
        Queue_buffer.put(one_batch, True)  # put with blocked
    m = q_info.get()
    Queue_buffer.cancel_join_thread()


def generator_n_batch_with_totpop(Queue_buffer, n_batch, q_info):
    '''
    sample n_batch without tot popularity
    '''
    all_users = list(data.train_user_list.keys())
    batch_size = data.batch_size
    for i in range(n_batch):
        batch_pos = []
        batch_neg = []
        batch_pop_pop = []
        batch_neg_pop = []
        if batch_size <= data.n_users:
            batch_users = rd.sample(all_users, batch_size)
        else:
            batch_users = [rd.choice(all_users) for _ in range(batch_size)]

        for u in batch_users:
            u_clicked_items = data.train_user_list[u]
            if u_clicked_items == []:
                batch_pos.append(0)
            else:
                batch_pos.append(rd.choice(u_clicked_items))
            while True:
                neg_item = rd.choice(data.items)
                if neg_item not in u_clicked_items:
                    batch_neg.append(neg_item)
                    break
        batch_pop_pop = data.expo_popularity[batch_pos]
        batch_neg_pop = data.expo_popularity[batch_neg]
        one_batch = (batch_users, batch_pos, batch_neg, batch_pop_pop, batch_neg_pop)
        # print("pos:", batch_pop_pop)
        # print("neg:", batch_neg_pop)
        Queue_buffer.put(one_batch, True)  # put with blocked
    m = q_info.get()
    Queue_buffer.cancel_join_thread()


# def generator_n_batch_with_pop(Queue_buffer,n_batch):
#     '''
#     sample n_batch data with popularity
#     '''
#     all_users = list(data.train_user_list.keys())
#     batch_size = data.batch_size
#     for i in range(n_batch):
#         batch_pos = []
#         batch_neg = []
#         batch_pos_pop = []
#         batch_neg_pop = []
#         if batch_size <= data.n_users:
#             batch_users = rd.sample(all_users, batch_size)
#         else:
#             batch_users = [rd.choice(all_users) for _ in range(batch_size)]
#         for u in batch_users:
#             u_clicked_items = data.train_user_list[u]
#             u_clicked_times = data.train_user_list_time[u]
#             if  u_clicked_items == []:
#                 one_pos_item = 0
#                 batch_pos.append(one_pos_item)
#                 u_pos_time = rd.choice(data.unique_times)
#             else:
#                 M_num = len(u_clicked_items)
#                 idx = np.random.randint(M_num)
#                 one_pos_item = u_clicked_items[idx]
#                 batch_pos.append(one_pos_item)
#                 u_pos_time = u_clicked_times[idx]
#             while True:
#                 neg_item = rd.choice(data.items)
#                 if neg_item not in u_clicked_items:
#                     batch_neg.append(neg_item)
#                     break
#             batch_pos_pop.append(data.expo_popularity[one_pos_item,u_pos_time])
#             batch_neg_pop.append(data.expo_popularity[neg_item,u_pos_time])
#         one_batch = (batch_users,batch_pos,batch_neg,batch_pos_pop,batch_neg_pop)
#         Queue_buffer.put(one_batch,True)  # put with blocked

def generator_n_batch_with_pop(Queue_buffer, n_batch, q_info):
    '''
    sample n_batch data with popularity
    '''
    # print('start')
    s_time = time()
    all_users = list(data.train_user_list.keys())
    batch_size = data.batch_size
    buffer = []
    for i in range(n_batch):
        batch_pos = []
        batch_neg = []
        batch_pos_pop = []
        batch_neg_pop = []
        if batch_size <= data.n_users:
            batch_users = rd.sample(all_users, batch_size)
        else:
            batch_users = [rd.choice(all_users) for _ in range(batch_size)]
        for u in batch_users:
            u_clicked_items = data.train_user_list[u]
            u_clicked_times = data.train_user_list_time[u]
            if u_clicked_items == []:
                one_pos_item = 0
                batch_pos.append(one_pos_item)
                u_pos_time = rd.choice(data.unique_times)
            else:
                M_num = len(u_clicked_items)
                idx = np.random.randint(M_num)
                one_pos_item = u_clicked_items[idx]
                batch_pos.append(one_pos_item)
                u_pos_time = u_clicked_times[idx]
            while True:
                neg_item = rd.choice(data.items)
                if neg_item not in u_clicked_items:
                    batch_neg.append(neg_item)
                    break
            batch_pos_pop.append(data.expo_popularity[one_pos_item, u_pos_time])
            batch_neg_pop.append(data.expo_popularity[neg_item, u_pos_time])
        one_batch = (batch_users, batch_pos, batch_neg, batch_pos_pop, batch_neg_pop)

        Queue_buffer.put(one_batch)
    # Queue_buffer.close()
    # for one_batch in buffer:
    #    Queue_buffer.put(one_batch)
    # print('end',s_time - time())
    m = q_info.get()
    Queue_buffer.cancel_join_thread()


def generator_n_batch_with_temp(Queue_buffer, n_batch, q_info):
    '''
    sample n_batch data with temp information
    '''
    # print('start')
    s_time = time()
    all_users = list(data.train_user_list.keys())
    batch_size = data.batch_size
    buffer = []
    batch_raw = np.arange(batch_size)
    for i in range(n_batch):
        batch_pos = []
        batch_neg = []
        batch_temp = []
        if batch_size <= data.n_users:
            batch_users = rd.sample(all_users, batch_size)
        else:
            batch_users = [rd.choice(all_users) for _ in range(batch_size)]
        for u in batch_users:
            u_clicked_items = data.train_user_list[u]
            u_clicked_times = data.train_user_list_time[u]
            if u_clicked_items == []:
                one_pos_item = 0
                batch_pos.append(one_pos_item)
                u_pos_time = rd.choice(data.unique_times)
            else:
                M_num = len(u_clicked_items)
                idx = np.random.randint(M_num)
                one_pos_item = u_clicked_items[idx]
                batch_pos.append(one_pos_item)
                u_pos_time = u_clicked_times[idx]
            while True:
                neg_item = rd.choice(data.items)
                if neg_item not in u_clicked_items:
                    batch_neg.append(neg_item)
                    break
            batch_temp.append(u_pos_time)
        one_batch = (batch_users, batch_pos, batch_neg, batch_temp, batch_raw)

        Queue_buffer.put(one_batch)
    m = q_info.get()
    Queue_buffer.cancel_join_thread()


def multi_sampling_user_with_time():
    worker = min(cores // max_pre, 10)
    worker = max(2, worker)
    pool = multiprocessing.Pool(worker)
    # except:
    #     print(type(all_users),len(all_users))
    #     raise ReferenceError("unknown error")
    batch_size = data.batch_size
    tot_num = data.n_train
    tot_batch = tot_num // batch_size + 1
    each_batch = tot_batch // worker + 1
    sub_sampel_batchs = [each_batch] * worker
    sampled_data = pool.map(sampling_one_user_one_with_time, sub_sampel_batchs)
    pool.close()
    pool.join()
    users = []
    pos_items = []
    neg_items = []
    pos_pop = []
    neg_pop = []
    for re in sampled_data:
        users.extend(re[0])
        pos_items.extend(re[1])
        neg_items.extend(re[2])
        pos_pop.extend(re[3])
        neg_pop.extend(re[4])
    for i in range(len(users)):
        yield (users[i], pos_items[i], neg_items[i], pos_pop[i], neg_pop[i])


def sampling_one_user_one_with_time(n_batch):
    # print(num)
    print('start..')
    s_time = time()
    all_users = list(data.train_user_list.keys())
    users = []
    pos_items = []
    neg_items = []
    pos_pop_tot = []
    neg_pop_tot = []
    batch_size = data.batch_size
    for i in range(n_batch):
        batch_pos = []
        batch_neg = []
        batch_pos_pop = []
        batch_neg_pop = []
        if batch_size <= data.n_users:
            batch_users = rd.sample(all_users, batch_size)
        else:
            batch_users = [rd.choice(all_users) for _ in range(batch_size)]
        for u in batch_users:
            u_clicked_items = data.train_user_list[u]
            u_clicked_times = data.train_user_list_time[u]
            if u_clicked_items == []:
                one_pos_item = 0
                batch_pos.append(one_pos_item)
                u_pos_time = rd.choice(data.unique_times)
            else:
                M_num = len(u_clicked_items)
                idx = np.random.randint(M_num)
                one_pos_item = u_clicked_items[idx]
                batch_pos.append(one_pos_item)
                u_pos_time = u_clicked_times[idx]
            while True:
                neg_item = rd.choice(data.items)
                if neg_item not in u_clicked_items:
                    batch_neg.append(neg_item)
                    break
            batch_pos_pop.append(data.expo_popularity[one_pos_item, u_pos_time])
            batch_neg_pop.append(data.expo_popularity[neg_item, u_pos_time])
        users.append(batch_users)
        pos_items.append(batch_pos)
        neg_items.append(batch_neg)
        pos_pop_tot.append(batch_pos_pop)
        neg_pop_tot.append(batch_neg_pop)
    print("end:", time() - s_time)
    return (users, pos_items, neg_items, pos_pop_tot, neg_pop_tot)


# def multi_sampling_user():
#     s_time = time()
#     worker = min(cores // max_pre,10)
#     worker = max(2,worker)
#     pool = multiprocessing.Pool(worker)
#     # except:
#     #     print(type(all_users),len(all_users))
#     #     raise ReferenceError("unknown error")
#     batch_size = data.batch_size
#     tot_num = data.n_train
#     tot_batch = tot_num // batch_size + 1
#     each_batch = tot_batch // worker + 1
#     sub_sampel_batchs = [ each_batch ] * worker
#     sampled_data  = pool.map(sampling_one_user_one,sub_sampel_batchs)
#     pool.close()
#     pool.join()
#     users = []
#     pos_items = []
#     neg_items = []
#     for re in sampled_data:
#         users.extend(re[0])
#         pos_items.extend(re[1])
#         neg_items.extend(re[2])
#     print("sampling cost time:",time()-s_time)
#     for i in range(len(users)):
#         yield (users[i],pos_items[i],neg_items[i])
# #    return users,pos_items,neg_items
# def sampling_one_user_one(n_batch):
#     #print(num)
#     all_users = list(data.train_user_list.keys())
#     users = []
#     pos_items = []
#     neg_items = []
#     batch_size = data.batch_size
#     for i in range(n_batch):
#         batch_pos = []
#         batch_neg = []
#         if batch_size <= data.n_users:
#             batch_users = rd.sample(all_users, batch_size)
#         else:
#             batch_users = [rd.choice(all_users) for _ in range(batch_size)]

#         for u in batch_users:
#             u_clicked_items = data.train_user_list[u]
#             if  u_clicked_items == []:
#                 batch_pos.append(0)
#             else:
#                 batch_pos.append(rd.choice(u_clicked_items))
#             while True:
#                 neg_item = rd.choice(data.items)
#                 if neg_item not in u_clicked_items:
#                     batch_neg.append(neg_item)
#                     break
#         users.append(batch_users)
#         pos_items.append(batch_pos)
#         neg_items.append(batch_neg)
#     return (users,pos_items,neg_items)


# @background(max_prefetch=20)
# def generator_with_Negsampling():
#     #print(num)
#     all_users = list(data.train_user_list.keys())
#     batch_size = data.batch_size
#     n_batch = data.n_train // batch_size
#     for i in range(n_batch):
#         batch_pos = []
#         batch_neg = []
#         if batch_size <= data.n_users:
#             batch_users = rd.sample(all_users, batch_size)
#         else:
#             batch_users = [rd.choice(all_users) for _ in range(batch_size)]

#         for u in batch_users:
#             u_clicked_items = data.train_user_list[u]
#             if  u_clicked_items == []:
#                 batch_pos.append(0)
#             else:
#                 batch_pos.append(rd.choice(u_clicked_items))
#             while True:
#                 neg_item = rd.choice(data.items)
#                 if neg_item not in u_clicked_items:
#                     batch_neg.append(neg_item)
#                     break
#         yield (batch_users,batch_pos,batch_neg)

# def generator_with_Negsampling_with_split_time():
#     all_users = list(data.train_user_list.keys())
#     batch_size = data.batch_size
#     n_batch = data.n_train // batch_size
#     for i in range(n_batch):
#         batch_pos = []
#         batch_neg = []
#         batch_time = []
#         batch_pos_pop = []
#         batch_neg_pop = []
#         if batch_size <= data.n_users:
#             batch_users = rd.sample(all_users, batch_size)
#         else:
#             batch_users = [rd.choice(all_users) for _ in range(batch_size)]
#         for u in batch_users:
#             u_clicked_items = data.train_user_list[u]
#             u_clicked_times = data.train_user_list_time[u]
#             if  u_clicked_items == []:
#                 one_pos_item = 0
#                 batch_pos.append(one_pos_item)
#                 u_pos_time = rd.choice(data.unique_times)
#                 batch_time.append(u_pos_time)
#             else:
#                 M_num = len(u_clicked_items)
#                 idx = np.random.randint(M_num)
#                 one_pos_item = u_clicked_items[idx]
#                 batch_pos.append(one_pos_item)
#                 u_pos_time = u_clicked_times[idx]
#                 batch_time.append(u_pos_time)
#             while True:
#                 neg_item = rd.choice(data.items)
#                 if neg_item not in u_clicked_items:
#                     batch_neg.append(neg_item)
#                     break
#             batch_pos_pop.append(data.expo_popularity[one_pos_item,u_pos_time])
#             batch_neg_pop.append(data.expo_popularity[neg_item,u_pos_time])
#         yield (batch_users,batch_pos,batch_neg,batch_pos_pop,batch_neg_pop)

class DatasetApi_Model():
    def __init__(self, args, data_config, test_batch, generator_sampler):
        super().__init__()
        self.test_users = tf.placeholder(tf.int32, shape=(1, None,))  # test one batch
        self.test_pos_items = tf.placeholder(tf.int32, shape=(1, None,))
        self.test_neg_items = tf.placeholder(tf.int32, shape=(1, None,))
        self.test_pos_pop = tf.placeholder(tf.float32,
                                           shape=(1, None,))  # temp for temp_pop model, and need cast to tf.int32
        self.test_neg_pop = tf.placeholder(tf.float32,
                                           shape=(1, None,))  # raw for tem_pop model, and need to cast to tf.int32

        if args.train == 's_condition' or args.train == 'condition' or args.train == 'temp_pop':
            self.input_type = "with_pop"
            print("dataset api with pop or temp")
            if args.train == 'temp_pop':
                self.input_type = 'with_temp'
            self.train_dataset = tf.data.Dataset.from_generator(generator_sampler,
                                                                (tf.int32, tf.int32, tf.int32, tf.float32, tf.float32),
                                                                (tf.TensorShape([None]), tf.TensorShape([None]),
                                                                 tf.TensorShape([None]), tf.TensorShape([None]),
                                                                 tf.TensorShape([None])))
            self.test_dataset = tf.data.Dataset.from_tensor_slices(
                (self.test_users, self.test_pos_items, self.test_neg_items, self.test_pos_pop, self.test_neg_pop))
        else:
            '''
            to be finished
            '''
            self.input_type = 'without_pop'
            print("dataset api without pop")
            self.train_dataset = tf.data.Dataset.from_generator(generator_sampler, (tf.int32, tf.int32, tf.int32), (
            tf.TensorShape([None]), tf.TensorShape([None]), tf.TensorShape([None])))
            self.test_dataset = tf.data.Dataset.from_tensor_slices(
                (self.test_users, self.test_pos_items, self.test_neg_items))

        self.train_dataset = self.train_dataset.prefetch(50)  # batch_size 1, the gernerator will form a batch
        # self.test_dataset = self.test_dataset.batch(test_batch) # batch_size : test batch

        self.iter_ = tf.data.Iterator.from_structure(self.train_dataset.output_types,
                                                     self.train_dataset.output_shapes)  # same for test dataset

        self.training_op = self.iter_.make_initializer(self.train_dataset)  # for each step, you must initlize this one
        self.testing_op = self.iter_.make_initializer(self.test_dataset)  # for each batch test, you need initied

        if args.train == 's_condition' or args.train == 'condition':
            self.user, self.pos_item, self.neg_item, self.pos_pop, self.neg_pop = self.iter_.get_next()
            self.Recommender = ConditionalBPRMF(args, data_config, use_dataset_api=True, users_api=self.user,
                                                pos_items_api=self.pos_item, \
                                                neg_items_api=self.neg_item, pos_pop_api=self.pos_pop,
                                                neg_pop_api=self.neg_pop)
        elif args.train == 'temp_pop':
            self.user, self.pos_item, self.neg_item, temp, raw = self.iter_.get_next()
            self.temp = tf.cast(temp, dtype=tf.int32)
            self.raw = tf.cast(raw, dtype=tf.int32)
            self.Recommender = BPRMFTempPop(args, data_config, use_dataset_api=True, users_api=self.user,
                                            pos_items_api=self.pos_item, neg_items_api=self.neg_item,
                                            temp_api=self.temp, raw_api=self.raw)
        else:
            '''
            to be finished
            '''
            self.user, self.pos_item, self.neg_item = self.iter_.get_next()
            if args.train == 'normal':
                self.Recommender = BPRMF(args, data_config, use_dataset_api=True, users_api=self.user,
                                         pos_items_api=self.pos_item, neg_items_api=self.neg_item)
            else:
                raise NotImplementedError("not implement this model: " + args.train)

        self.Create_Recommendation()

    def Create_Recommendation(self, topk_max=50):

        self.sparse_cliked_matrix = tf.sparse.placeholder(tf.float32)  # tf.sparse_placeholder(tf.float32)
        # main_branch result
        self.main_branchRec_rating = tf.sparse.add(self.Recommender.batch_ratings, self.sparse_cliked_matrix)
        _, self.main_brach_topk_idx = tf.nn.top_k(self.main_branchRec_rating, topk_max)  # topk

        # main_branch result with pop
        actived_main_rating = tf.add(tf.nn.elu(self.Recommender.batch_ratings), tf.constant(1.0))  # activate
        main_rating_with_pop = tf.multiply(actived_main_rating, tf.squeeze(self.test_pos_pop))
        self.main_with_pop_Recrating = tf.sparse.add(main_rating_with_pop, self.sparse_cliked_matrix)
        _, self.main_with_pop_topk_idx = tf.nn.top_k(self.main_with_pop_Recrating, topk_max)  # topk

        # condition recommendation
        try:
            self.conditionRec_reting = tf.sparse.add(self.Recommender.condition_ratings, self.sparse_cliked_matrix)
            _, self.condition_topk_idx = tf.nn.top_k(self.conditionRec_reting, k=topk_max)
        except:
            self.conditionRec_reting = None
            self.condition_topk_idx = None

    def do_recommendation(self, sess, batch_users, items, rec_type, pos_pop=None, sparse_cliked_matrix=None):
        # print(len(batch_users),sparse_cliked_matrix[2])
        batch_users = [batch_users]
        items = [items]
        if pos_pop is not None:
            pos_pop = pos_pop.reshape(1, -1)
        else:
            pos_pop = [[0]]
        # input with or without pop according model.Recommmender
        if self.input_type == 'with_pop':
            feed_dict = feed_dict = {self.test_users: batch_users, self.test_pos_items: items,
                                     self.test_neg_items: [[0]], self.test_pos_pop: pos_pop, self.test_neg_pop: [[0]]}
        elif self.input_type == 'with_temp':  # temp pop
            temp = [[0]]  # taking the last stage temp as input in model, don't need input
            raw = [[0]]
            feed_dict = feed_dict = {self.test_users: batch_users, self.test_pos_items: items,
                                     self.test_neg_items: [[0]], self.test_pos_pop: temp, self.test_neg_pop: raw}
        else:
            feed_dict = {self.test_users: batch_users, self.test_pos_items: items, self.test_neg_items: [[0]]}
        self.switch_to_testing_or_reinit(sess, feed_dict)  # switch to test dataset api
        if rec_type == 'main_branch':
            topk_items = sess.run(self.main_brach_topk_idx, feed_dict={self.sparse_cliked_matrix: sparse_cliked_matrix})
        elif rec_type == 'main_with_pop':
            topk_items = sess.run(self.main_with_pop_topk_idx,
                                  feed_dict={self.sparse_cliked_matrix: sparse_cliked_matrix,
                                             self.test_pos_pop: pos_pop})
        elif rec_type == 'condition':
            topk_items = sess.run(self.condition_topk_idx, feed_dict={self.sparse_cliked_matrix: sparse_cliked_matrix})
        else:
            raise NotImplementedError("we have only implement recommendation method: main main+pop condition")
        return topk_items

    def testing(self, sess, batch_users, items, model_type, pos_pop=None):
        # print("batch_users:",batch_users)
        # print("batch_items:",items)
        batch_users = [batch_users]
        items = [items]
        if pos_pop is not None:
            pos_pop = pos_pop.reshape(1, -1)
        else:
            pos_pop = [[0]]
        # input with or without pop according model.Recommmender
        if self.input_type == 'with_pop':
            feed_dict = {self.test_users: batch_users, self.test_pos_items: items, self.test_neg_items: [[0]],
                         self.test_pos_pop: pos_pop, self.test_neg_pop: [[0]]}
        else:
            feed_dict = {self.test_users: batch_users, self.test_pos_items: items, self.test_neg_items: [[0]]}
        # testing...............................................
        if model_type == 'main_branch':  # only consider interest branch
            self.switch_to_testing_or_reinit(sess, feed_dict)
            scores = sess.run(self.Recommender.batch_ratings)
        elif model_type == 'condition':
            self.switch_to_testing_or_reinit(sess, feed_dict)
            scores = sess.run(self.Recommender.condition_ratings)
        else:
            raise NotImplementedError("error -- not implement this type testing method...")
        # print('score shape:',scores)
        # if type(scores) is not np.ndarray:
        #     scores = np.array(scores)
        #     print("scores shape:",scores)
        return scores

    def switch_to_training_or_reinitsampler(self, sess):
        sess.run(self.training_op)

    def switch_to_testing_or_reinit(self, sess, feed_dict):
        sess.run(self.testing_op, feed_dict=feed_dict)

    def set_testing_way(self, model_type, popularity_exp):
        self.testing_model_type = model_type
        self.testing_popularity = popularity_exp

    def set_sess(self, sess):
        self.sess = sess

    def predict(self, user_batch, item_batch):
        model_type = self.testing_model_type
        sess = self.sess
        if item_batch == None:
            item_batch = list(range(ITEM_NUM))
        if model_type == 'o':
            model_type = 'main_branch'
            scores = self.testing(sess, user_batch, item_batch, model_type, pos_pop=None)
        elif model_type == 'condition':
            pos_pop = self.testing_popularity[item_batch]
            scores = self.testing(sess, user_batch, item_batch, model_type, pos_pop=pos_pop)
        else:
            raise NotImplementedError("not implement this type testing methods")
        return scores


def gen_xquad_result(sess, model):
    pass


class evaluation():
    def __init__(self) -> None:
        super().__init__()
        self.batch_size = 2048
        self.set_evaluate_obj()
        self.testing_popularity = None

    def set_evaluate_obj(self, eval_who='test'):
        self.eval_who = eval_who

    def set_testing_popularity(self, popularity):
        self.testing_popularity = popularity

    def set_evaluate_obj_pre(self, eval_who='test'):
        self.eval_who = eval_who
        if eval_who == 'test':
            self.eval_user_list = data.test_user_list
        else:
            self.eval_user_list = data.valid_user_list
        self.list_batch_user = []
        self.list_batch_index = []
        all_users = list(self.eval_user_list.keys())
        self.tot_user = len(all_users)
        tot_users = self.tot_user
        for i in range(0, tot_users, self.batch_size):
            end_idx = min(i + self.batch_size, tot_users)
            batch_user = all_users[i:end_idx]
            clicked_items = []
            clicked_num = []
            N_ = len(batch_user)
            for u in batch_user:
                m = data.train_user_list[u]
                clicked_items.extend(m)
                clicked_num.append(len(m))
            self.list_batch_user.append(batch_user)
            batch_user_padding = list(np.repeat(list(range(N_)), clicked_num))
            index = np.array([batch_user_padding, clicked_items]).astype(np.int64).T
            valu_num = len(batch_user_padding)
            row_num = N_
            self.list_batch_index.append((index, row_num, valu_num))

    def test_one_batch(self, batch_result):
        batch_user, batch_rec = batch_result
        result = {'precision': np.zeros(len(Ks)), 'recall': np.zeros(len(Ks)), 'ndcg': np.zeros(len(Ks)),
                  'hit_ratio': np.zeros(len(Ks))}
        for i in range(len(batch_user)):
            u = batch_user[i]
            r = batch_rec[i]
            try:
                u_target = self.eval_user_list[u]
            except:
                u_target = []
            one_user_result = get_performance(u_target, r, Ks)

            result['precision'] += one_user_result['precision']
            result['recall'] += one_user_result['recall']
            result['ndcg'] += one_user_result['ndcg']
            result['hit_ratio'] += one_user_result['hit_ratio']
        return result

    def eval(self, model, sess, rec_type):
        result = {'precision': np.zeros(len(Ks)), 'recall': np.zeros(len(Ks)), 'ndcg': np.zeros(len(Ks)),
                  'hit_ratio': np.zeros(len(Ks))}
        pool = multiprocessing.Pool(5)
        res = []
        # self.generator_Rec_result_fast(model,sess,rec_type)
        res = pool.map(self.test_one_batch, self.generator_Rec_result_fast(model, sess, rec_type))
        #  res = pool.map(self.test_one_batch,self.rec_result)
        # for (batch_user,batch_rec) in self.generator_Rec_result_fast(model,sess,rec_type):
        #     res.append(pool.apply_async(self.test_one_batch,args=(batch_user,batch_rec,)))
        pool.close()
        pool.join()
        for re in res:
            # re = re_.get()
            result['precision'] += re['precision'] / self.tot_user
            result['recall'] += re['recall'] / self.tot_user
            result['ndcg'] += re['ndcg'] / self.tot_user
            result['hit_ratio'] += re['hit_ratio'] / self.tot_user
        return result

    def generator_Rec_result_fast(self, model, sess, rec_type):
        i = 0
        result = []
        ttt1 = time()
        for batch_user in self.list_batch_user:
            batch_item = list(range(ITEM_NUM))
            index, row_num, valu_num = self.list_batch_index[i]
            if self.testing_popularity is not None:
                pos_pop = self.testing_popularity[batch_item]
            else:
                pos_pop = None
            sparse_cliked_matrix = (
            index, np.array([-np.inf] * valu_num).astype(np.float32), np.array([row_num, ITEM_NUM]).astype(np.int64))
            batch_topk = model.do_recommendation(sess, batch_user, batch_item, rec_type, pos_pop=pos_pop,
                                                 sparse_cliked_matrix=sparse_cliked_matrix)
            i += 1
            yield (batch_user, batch_topk)
        #     result.append((batch_user,batch_topk))
        # print("inference time:",time()-ttt1)
        # self.rec_result = result

        # return result
        # for re in result:
        #     yield re

    def generator_Rec_result(self, model, sess, rec_type):
        if self.eval_who == 'test':
            eval_list = data.test_user_list
        else:
            eval_list = data.valid_user_list

        all_users = list(eval_list.keys())
        tot_users = len(all_users)
        self.tot_user = tot_users
        for i in range(0, tot_users, self.batch_size):
            end_idx = min(i + self.batch_size, tot_users)
            batch_user = all_users[i:end_idx]
            clicked_items = []
            clicked_num = []
            for u in batch_user:
                m = eval_list[u]
                clicked_items.extend(m)
                clicked_num.append(len(m))
            batch_item = item_batch = list(range(ITEM_NUM))
            if self.testing_popularity is not None:
                pos_pop = self.testing_popularity[item_batch]
            else:
                pos_pop = None
            sparse_cliked_matrix = (np.repeat(list(rang(len(batch_user))), cliked_num), np.array(cliked_items),
                                    np.array([-np.inf] * len(clicked_items)))
            batch_topk = model.do_recommendation(sess, batch_user, batch_item, rec_type, pos_pop=pos_pop,
                                                 sparse_cliked_matrix=sparse_cliked_matrix)
            yield (batch_user, batch_topk)


# class predict_model(object):
#     def __init__(self,model,model_type):
#         self.model = model
#         self.model_type = model_type
#         self.item_pop_test = None
#         self.pop_exp = None
#         self.ori_input = tf.placeholder(tf.float32, shape = (None,ITEM_NUM))
#         self.topk_result = tf.nn.top_k(self.ori_input,k=100)
#         self.need_save = False
#         self.result = []
#         self.popularity = None

#     def update_pop_exp(self,pop_exp):
#         self.pop_exp = pop_exp
#         self.item_pop_test_exp = np.power(self.item_pop_test, pop_exp)

#     def predict(self,sess,user_batch,item_batch):
#         model_type = self.model_type
#         if item_batch==None:
#             item_batch = list(range(ITEM_NUM))
#         if model_type == 'o':
#             model_type = 'main_branch'
#             scores = self.model.testing(sess,user_batch,item_batch,model_type, pos_pop = None)
#         elif model_type == 'condition':
#             pos_pop = self.popularity[item_batch]
#             scores = self.model.testing(sess,user_batch,item_batch,model_type, pos_pop = pos_pop)
#         else:
#             raise NotImplementedError("not implement this type testing methods")
#         return scores

def load_popularity(args):
    r_path = args.data_path + args.dataset + "/"
    pop_save_path = r_path + "item_pop_seq_ori2.txt"
    if not os.path.exists(pop_save_path):
        pop_save_path = r_path + "item_pop_seq_ori.txt"
    print("popularity used:", pop_save_path)
    with open(pop_save_path) as f:
        print("pop save path: ", pop_save_path)
        item_list = []
        pop_item_all = []
        for line in f:
            line = line.strip().split()
            item, pop_list = int(line[0]), [float(x) for x in line[1:]]
            item_list.append(item)
            pop_item_all.append(pop_list)
    pop_item_all = np.array(pop_item_all)
    print("pop_item_all shape:", pop_item_all.shape)
    print("load pop information:", pop_item_all.mean(), pop_item_all.max(), pop_item_all.min())
    return pop_item_all


def get_dataset_tot_popularity():
    popularity_matrix = np.zeros(data.n_items).astype(np.float)
    for a_item, clicked_users in data.train_item_list.items():
        popularity_matrix[a_item] = len(clicked_users)
    popularity_matrix = popularity_matrix.astype(np.float)
    popularity_matrix += 1.0
    popularity_matrix /= popularity_matrix.sum()
    popularity_matrix = (popularity_matrix - popularity_matrix.min()) / (
                popularity_matrix.max() - popularity_matrix.min())
    print("popularity information-- mean:{},max:{},min:{}".format(popularity_matrix.mean(), popularity_matrix.max(),
                                                                  popularity_matrix.min()))
    # popularity_matrix = np.power(popularity_matrix,popularity_exp)
    # print("After power,popularity information-- mean:{},max:{},min:{}".format(popularity_matrix.mean(),popularity_matrix.max(),popularity_matrix.min()))
    return popularity_matrix


def get_popularity_from_load(item_pop_all):
    popularity_matrix = item_pop_all[:, :-1]  # don't contain the popularity in test stages
    print("------ popularity information --------")
    print("   each stage mean:", popularity_matrix.mean(axis=0))
    print("   each stage max:", popularity_matrix.max(axis=0))
    print("   each stage min:", popularity_matrix.min(axis=0))
    # popularity_matrix = np.power(popularity_matrix,popularity_exp)  # don't contain the popullarity for test stages...
    # print("------ popularity information after power  ------")
    # print("   each stage mean:",popularity_matrix.mean(axis=0))
    # print("   each stage max:",popularity_matrix.max(axis=0))
    # print("   each stage min:",popularity_matrix.min(axis=0))
    return popularity_matrix


def early_stop(hr, ndcg, recall, precision, cur_epoch, config, stopping_step, flag_step=10):
    if recall >= config['best_recall']:
        stopping_step = 0
        config['best_hr'] = hr
        config['best_ndcg'] = ndcg
        config['best_recall'] = recall
        config['best_pre'] = precision
        config['best_epoch'] = cur_epoch
    else:
        stopping_step += 1

    if stopping_step >= flag_step:
        print("Early stopping is trigger")
        should_stop = True
    else:
        should_stop = False
    return config, stopping_step, should_stop


if __name__ == '__main__':
    # random.seed(123)
    # tf.set_random_seed(123)

    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.cuda)
    config = dict()
    config['n_users'] = data.n_users
    config['n_items'] = data.n_items
    model_type = ''
    print("data size:", sys.getsizeof(data) / (10 ** 6), "GB")
    # ----------  important parameters -------------------------
    popularity_exp = args.pop_exp
    print("----- popularity_exp : ", popularity_exp)
    test_batch_size = min(1024, args.batch_size)

    # ------------  pre computed popularity ------------------
    pop_item_all = load_popularity(args)
    # popularity for test...
    last_stage_popualarity = pop_item_all[:, -2]
    last_stage_popualarity = np.power(last_stage_popualarity, popularity_exp)  # laste stage popularity (method a)
    alpha_pre = 0.5
    if args.dataset == "douban":
        alpha_pre = 0.01
    linear_predict_popularity = pop_item_all[:, -2] + alpha_pre * (
                pop_item_all[:, -2] - pop_item_all[:, -3])  # predicted popularity (method b)
    linear_predict_popularity[np.where(linear_predict_popularity <= 0)] = 1e-9
    linear_predict_popularity[np.where(linear_predict_popularity > 1.0)] = 1.0
    linear_predict_popularity = np.power(linear_predict_popularity, popularity_exp)

    # Train_generator = Train_data_generator()
    # ---------------  set model ----------------
    regs_pretain = args.regs
    if args.model == 'mf' and args.train == 'normal':  # BPR model
        args.saveID += "pop_exp-{:.2f}".format(popularity_exp)
        print("normal MF... ")
        regs_pretain = args.regs
        args.regs = args.fregs
        model = DatasetApi_Model(args, config, test_batch_size, multi_generator_finetune)  # multi_generator
        last_stage_popualarity_ori = pop_item_all[:, -2]
        linear_predict_popularity_ori = pop_item_all[:, -2] + alpha_pre * (
                    pop_item_all[:, -2] - pop_item_all[:, -3])  # predicted popularity
        linear_predict_popularity_ori[np.where(linear_predict_popularity <= 0)] = 1e-9
        linear_predict_popularity_ori[np.where(linear_predict_popularity > 1.0)] = 1.0

    elif args.model == 'mf' and args.train == 's_condition':  # PD & PDA model
        print('-------    running s\_condition  ----------------')
        args.saveID += "pop_exp-{:.2f}".format(popularity_exp)
        print("save_ID", args.saveID)
        popularity_matrix = get_popularity_from_load(pop_item_all)
        popularity_matrix = np.power(popularity_matrix, popularity_exp)
        print("------ popularity information after power  ------")
        print("   each stage mean:", popularity_matrix.mean(axis=0))
        print("   each stage max:", popularity_matrix.max(axis=0))
        print("   each stage min:", popularity_matrix.min(axis=0))
        model_type == 'mf'
        model = DatasetApi_Model(args, config, test_batch_size, multi_generator_with_pop2)
        data.add_expo_popularity(popularity_matrix)

    vars_to_restore = []
    for var in tf.trainable_variables():
        if "item_embedding" in var.name:
            vars_to_restore.append(var)
    saver = tf.train.Saver(max_to_keep=10000)
    gpu_config = tf.ConfigProto()
    gpu_config.gpu_options.allow_growth = True
    sess = tf.Session(config=gpu_config)
    sess.run(tf.global_variables_initializer())
    model.set_sess(sess)
    args.wd = regs_pretain
    # ------------    put model to test model

    filter_new_in_train = True

    evaluation_model = evaluation()
    if args.valid_set == "test":
        evaluation_model.set_evaluate_obj_pre('test')
        print("valid in test set")
    elif args.valid_set == "valid":
        print("valid in valid set")
        evaluation_model.set_evaluate_obj_pre('valid')
    else:
        print('evaluate type error.')
        exit()

    print("args info:", args)
    # print("metric info:",evaluator_.metrics_info())
    print("top K:", Ks)

    # -----------training without pretrain----------
    best_pop_expo_normal = 0

    if args.train == 's_condition': # reproduce PD & PDA
        in_last_pop = last_stage_popualarity
        in_linear_pop = linear_predict_popularity
        stopping_step = 0
        save_dir = args.save_dir


        def print_result_f(ret):
            perf_str = '||---------------------------------------------- recall=[%.5f, %.5f], precision=[%.5f, %.5f], hit=[%.5f, %.5f], ndcg=[%.5f, %.5f]' % \
                       (ret['recall'][0], ret['recall'][-1], ret['precision'][0], ret['precision'][-1],
                        ret['hit_ratio'][0], ret['hit_ratio'][-1],
                        ret['ndcg'][0], ret['ndcg'][-1])
            print(perf_str)
        evaluation_model.set_evaluate_obj_pre('test')  # set the evaluated dataset valid or test

        ###
        """
        |-------- reproduce PD result --------|
        """
        print("|---- reproduce PD  ------|")
        save_ckpt_dir = save_dir + args.dataset + "/" + "PD/"
        print("loading trained model")
        saver.restore(sess, save_ckpt_dir + "best_main_ckpt.ckpt")
        print("best main result:")
        evaluation_model.set_testing_popularity(None)
        ret = evaluation_model.eval(model, sess, rec_type='main_branch')
        print("---- PD result:")
        print_result_f(ret)

        # reproduce PDA
        """
        |-------- reproduce PDA result --------|
        """
        print("|---- reproduce PDA  ------|")
        save_ckpt_dir = save_dir + args.dataset+"/"+"PDA/"
        print("loading trained model....")
        saver.restore(sess, save_ckpt_dir + "best_ckpt.ckpt")
        ttt1 = time()
        evaluation_model.set_testing_popularity(in_last_pop)
        ret1 = evaluation_model.eval(model, sess, rec_type='condition')
        print("||------------ PDA with last stage popularity: time: ", int(time() - ttt1))
        print_result_f(ret1)
        # ret2 = condition_test(evaluator_,model,test_model = condition_type, popularity = in_last_pop)
        ttt1 = time()
        evaluation_model.set_testing_popularity(in_linear_pop)
        ret2 = evaluation_model.eval(model, sess, rec_type='condition')
        print("||------------ PDA with linear predicted popularity: time: ", int(time() - ttt1))
        print_result_f(ret2)
        ret = ret1

    if args.train == 'normal': # reproduce PD & PDA
        save_dir = args.save_dir
        def print_result_f(ret):
            perf_str = '||---------------------------------------------- recall=[%.5f, %.5f], precision=[%.5f, %.5f], hit=[%.5f, %.5f], ndcg=[%.5f, %.5f]' % \
                       (ret['recall'][0], ret['recall'][-1], ret['precision'][0], ret['precision'][-1],
                        ret['hit_ratio'][0], ret['hit_ratio'][-1],
                        ret['ndcg'][0], ret['ndcg'][-1])
            print(perf_str)

        evaluation_model.set_evaluate_obj_pre('test') # evaluated objective

        """
        |-------- reproduce BPRMF result --------|
        """
        print("|-------- reproduce BPRMF result --------|")
        save_ckpt_dir = save_dir + args.dataset + "/" + "BPRMF/"
        print("loading prtraining model")
        saver.restore(sess, save_ckpt_dir + "best_main_ckpt.ckpt")
        print(".............testing....................")
        evaluation_model.set_testing_popularity(None)
        ret = evaluation_model.eval(model, sess, rec_type='main_branch')
        print("----BPRMF result without adjusting pop:")
        best_ret = ret.copy()
        print_result_f(ret)


        # '''
        # |-------- BPRMF-A result -------- |
        # '''
        # print("|-------- BPRMF-A result -------- |")
        # save_ckpt_dir = save_dir + args.dataset + "/" + "BPRMF-A/"
        # print("loading trained model")
        # saver.restore(sess, save_ckpt_dir + "best_ckpt.ckpt")
        #
        # pop_used = np.power(last_stage_popualarity_ori, best_pop_expo_normal) # use prediction method (a) for desired popularity
        # evaluation_model.set_testing_popularity(pop_used)
        # ret = evaluation_model.eval(model, sess, rec_type='main_with_pop')
        # print("---- BPRMF-A result without last stage pop:")
        # print_result_f(ret)
        #
        # pop_used = np.power(linear_predict_popularity_ori, best_pop_expo_normal) # use prediction method (b) for desired popularity
        # evaluation_model.set_testing_popularity(pop_used)
        # ret = evaluation_model.eval(model, sess, rec_type='main_with_pop')
        # print("---- BPRMF-A result without linear predicted pop:")
        # print_result_f(ret)
