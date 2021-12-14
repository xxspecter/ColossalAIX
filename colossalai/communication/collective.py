#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import torch
import torch.distributed as dist
from torch import Tensor

from colossalai.context import ParallelMode
from colossalai.core import global_context as gpc
from colossalai.utils import get_current_device


def all_gather(tensor: Tensor, dim: int,
               parallel_mode: ParallelMode, async_op=False) -> Tensor:
    """Gathers all tensors from the parallel group and concatenates them in a 
    specific dimension.
    
    :param tensor: Tensor to be gathered
    :param dim: The dimension concatenating in
    :param parallel_mode: Parallel group mode used in this communication
    :type tensor: :class:`torch.Tensor`
    :type dim: int
    :type parallel_mode: :class:`colossalai.context.ParallelMode`
    :return: The tensor generated by all-gather
    :rtype: :class:`torch.Tensor`
    """
    depth = gpc.get_world_size(parallel_mode)
    temp = tensor.clone()
    # shape = list(temp.shape)
    # shape[dim] *= depth
    # out = torch.zeros(shape, dtype=temp.dtype, device=get_current_device())
    # out = list(torch.chunk(out, depth, dim=dim))
    # out = [val.contiguous() for val in out]
    shape = [1] * len(tensor.shape)
    shape[dim] = depth
    out = tensor.repeat(shape)
    out = list(map(lambda x: x.contiguous(), torch.chunk(out, depth, dim=dim)))
    op = dist.all_gather(tensor_list=out,
                         tensor=temp,
                         group=gpc.get_group(parallel_mode),
                         async_op=async_op)
    # out = torch.cat(out, dim=dim)
    if async_op:
        return out, op
    else:
        return out


def reduce_scatter(tensor: Tensor, dim: int,
                   parallel_mode: ParallelMode, async_op=False) -> Tensor:
    """Reduces all tensors then scatters it in a specific dimension to all 
    members in the parallel group.
    
    :param tensor: Tensor to be reduced and scattered
    :param dim: The dimension scattering in
    :param parallel_mode: Parallel group mode used in this communication
    :type tensor: :class:`torch.Tensor`
    :type dim: int
    :type parallel_mode: :class:`colossalai.context.ParallelMode`
    :return: The tensor generated by reduce-scatter
    :rtype: :class:`Tensor`
    """
    depth = gpc.get_world_size(parallel_mode)
    # temp = list(torch.chunk(tensor, depth, dim=dim))
    # temp = [val.contiguous() for val in temp]
    # out = torch.zeros(temp[0].shape,
    #                   dtype=temp[0].dtype,
    #                   device=get_current_device())
    temp = list(map(lambda x: x.contiguous(), torch.chunk(tensor, depth, dim=dim)))
    out = temp[0].clone()
    op = dist.reduce_scatter(output=out,
                             input_list=temp,
                             group=gpc.get_group(parallel_mode),
                             async_op=async_op)
    if async_op:
        return out, op
    else:
        return out


def all_reduce(tensor: Tensor,
               parallel_mode: ParallelMode,
               async_op=False) -> Tensor:
    op = dist.all_reduce(tensor,
                         group=gpc.get_group(parallel_mode),
                         async_op=async_op)
    if async_op:
        return tensor, op
    else:
        return tensor


# def scatter(tensor: Tensor, src: int, dim: int,
#             parallel_mode: ParallelMode) -> Tensor:
#     """Scatters in a specific dimension from source rank to all ranks in 
#     the parallel group.
    
#     :param tensor: Tensor to be scattered
#     :param dim: The dimension scattering in
#     :param parallel_mode: Parallel group mode used in this communication
#     :type tensor: Tensor
#     :type dim: int
#     :type parallel_mode: ParallelMode
#     :return: The tensor generated by scatter
#     :rtype: Tensor
#     """
#     depth = gpc.get_world_size(parallel_mode)
#     temp = tensor.clone()
#     dist.broadcast(temp, src=src, group=gpc.get_group(parallel_mode))
#     rank = gpc.get_local_rank(parallel_mode)
#     out = torch.chunk(temp, depth, dim=dim)[rank].contiguous()
#     return out