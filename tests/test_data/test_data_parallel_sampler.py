#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import os
from functools import partial
from pathlib import Path

import pytest
import torch.cuda
import torch.distributed as dist
import torch.multiprocessing as mp
from torch.utils.data import DataLoader

import colossalai
from colossalai.builder import build_dataset, build_data_sampler, build_transform
from torchvision import transforms
from colossalai.context import ParallelMode, Config
from colossalai.core import global_context as gpc
from colossalai.utils import get_dataloader

CONFIG = Config(
    dict(
        train_data=dict(
            dataset=dict(
                type='CIFAR10',
                root=Path(os.environ['DATA']),
                train=True,
                download=True,
            ),
            dataloader=dict(
                batch_size=8,
            ),
            transform_pipeline=[
                dict(type='ToTensor'),
                dict(type='Normalize', mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5))
            ]
        ),
        parallel=dict(
            pipeline=dict(size=1),
            tensor=dict(size=1, mode=None),
        ),
        seed=1024,
    ))


def run_data_sampler(rank, world_size):
    dist_args = dict(
        config=CONFIG,
        rank=rank,
        world_size=world_size,
        backend='gloo',
        port='29503',
        host='localhost'
    )
    colossalai.launch(**dist_args)
    print('finished initialization')

    transform_pipeline = [build_transform(cfg) for cfg in gpc.config.train_data.transform_pipeline]
    transform_pipeline = transforms.Compose(transform_pipeline)
    gpc.config.train_data.dataset['transform'] = transform_pipeline
    dataset = build_dataset(gpc.config.train_data.dataset)
    dataloader = get_dataloader(dataset, **gpc.config.train_data.dataloader)
    data_iter = iter(dataloader)
    img, label = data_iter.next()
    img = img[0]

    if gpc.get_local_rank(ParallelMode.DATA) != 0:
        img_to_compare = img.clone()
    else:
        img_to_compare = img
    dist.broadcast(img_to_compare, src=0, group=gpc.get_group(ParallelMode.DATA))

    if gpc.get_local_rank(ParallelMode.DATA) != 0:
        assert not torch.equal(img,
                               img_to_compare), 'Same image was distributed across ranks but expected it to be different'


@pytest.mark.cpu
def test_data_sampler():
    world_size = 4
    test_func = partial(run_data_sampler, world_size=world_size)
    mp.spawn(test_func, nprocs=world_size)


if __name__ == '__main__':
    test_data_sampler()