# Copyright (c) 2020 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
from paddle import fluid
from paddle.fluid.param_attr import ParamAttr
from paddle.fluid.initializer import Normal
from paddle.fluid.regularizer import L2Decay
from paddle.fluid.initializer import Constant

__all__ = ['RPNHead', 'FPNRPNHead']


class RPNHead(object):
    def __init__(
            self,
            #anchor_generator
            stride=[16.0, 16.0],
            anchor_sizes=[32, 64, 128, 256, 512],
            aspect_ratios=[0.5, 1., 2.],
            variance=[1., 1., 1., 1.],
            #rpn_target_assign
            rpn_batch_size_per_im=256,
            rpn_straddle_thresh=0.,
            rpn_fg_fraction=0.5,
            rpn_positive_overlap=0.7,
            rpn_negative_overlap=0.3,
            use_random=True,
            rpn_cls_loss='SigmoidCrossEntropy',
            rpn_focal_loss_gamma=2,
            rpn_focal_loss_alpha=0.25,
            #train_proposal
            train_pre_nms_top_n=12000,
            train_post_nms_top_n=2000,
            train_nms_thresh=.7,
            train_min_size=.0,
            train_eta=1.,
            #test_proposal
            test_pre_nms_top_n=6000,
            test_post_nms_top_n=1000,
            test_nms_thresh=.7,
            test_min_size=.0,
            test_eta=1.,
            #num_classes
            num_classes=1):
        super(RPNHead, self).__init__()
        self.stride = stride
        self.anchor_sizes = anchor_sizes
        self.aspect_ratios = aspect_ratios
        self.variance = variance
        self.rpn_batch_size_per_im = rpn_batch_size_per_im
        self.rpn_straddle_thresh = rpn_straddle_thresh
        self.rpn_fg_fraction = rpn_fg_fraction
        self.rpn_positive_overlap = rpn_positive_overlap
        self.rpn_negative_overlap = rpn_negative_overlap
        self.use_random = use_random
        self.train_pre_nms_top_n = train_pre_nms_top_n
        self.train_post_nms_top_n = train_post_nms_top_n
        self.train_nms_thresh = train_nms_thresh
        self.train_min_size = train_min_size
        self.train_eta = train_eta
        self.test_pre_nms_top_n = test_pre_nms_top_n
        self.test_post_nms_top_n = test_post_nms_top_n
        self.test_nms_thresh = test_nms_thresh
        self.test_min_size = test_min_size
        self.test_eta = test_eta
        self.num_classes = num_classes
        self.rpn_cls_loss = rpn_cls_loss
        self.rpn_focal_loss_gamma = rpn_focal_loss_gamma
        self.rpn_focal_loss_alpha = rpn_focal_loss_alpha

    def _get_output(self, input):
        """
        Get anchor and RPN head output.

        Args:
            input(Variable): feature map from backbone with shape of [N, C, H, W]

        Returns:
            rpn_cls_score(Variable): Output of rpn head with shape of
                [N, num_anchors, H, W].
            rpn_bbox_pred(Variable): Output of rpn head with shape of
                [N, num_anchors * 4, H, W].
        """
        dim_out = input.shape[1]
        rpn_conv = fluid.layers.conv2d(
            input=input,
            num_filters=dim_out,
            filter_size=3,
            stride=1,
            padding=1,
            act='relu',
            name='conv_rpn',
            param_attr=ParamAttr(
                name="conv_rpn_w", initializer=Normal(
                    loc=0., scale=0.01)),
            bias_attr=ParamAttr(
                name="conv_rpn_b", learning_rate=2., regularizer=L2Decay(0.)))
        # Generate anchors
        self.anchor, self.anchor_var = fluid.layers.anchor_generator(
            input=rpn_conv,
            stride=self.stride,
            anchor_sizes=self.anchor_sizes,
            aspect_ratios=self.aspect_ratios,
            variance=self.variance)
        num_anchor = self.anchor.shape[2]
        # Proposal classification scores
        if self.rpn_cls_loss == 'SigmoidCrossEntropy':
            bias_init = None
        elif self.rpn_cls_loss == 'SigmoidFocalLoss':
            value = float(-np.log((1 - 0.01) / 0.01))
            bias_init = Constant(value=value)
        self.rpn_cls_score = fluid.layers.conv2d(
            rpn_conv,
            num_filters=num_anchor * self.num_classes,
            filter_size=1,
            stride=1,
            padding=0,
            act=None,
            name='rpn_cls_score',
            param_attr=ParamAttr(
                name="rpn_cls_logits_w",
                initializer=Normal(
                    loc=0., scale=0.01)),
            bias_attr=ParamAttr(
                name="rpn_cls_logits_b",
                initializer=bias_init,
                learning_rate=2.,
                regularizer=L2Decay(0.)))
        # Proposal bbox regression deltas
        self.rpn_bbox_pred = fluid.layers.conv2d(
            rpn_conv,
            num_filters=4 * num_anchor,
            filter_size=1,
            stride=1,
            padding=0,
            act=None,
            name='rpn_bbox_pred',
            param_attr=ParamAttr(
                name="rpn_bbox_pred_w", initializer=Normal(
                    loc=0., scale=0.01)),
            bias_attr=ParamAttr(
                name="rpn_bbox_pred_b",
                learning_rate=2.,
                regularizer=L2Decay(0.)))
        return self.rpn_cls_score, self.rpn_bbox_pred

    def get_proposals(self, body_feats, im_info, mode='train'):
        """
        Get proposals according to the output of backbone.

        Args:
            body_feats (dict): The dictionary of feature maps from backbone.
            im_info(Variable): The information of image with shape [N, 3] with
                shape (height, width, scale).
            body_feat_names(list): A list of names of feature maps from
                backbone.

        Returns:
            rpn_rois(Variable): Output proposals with shape of (rois_num, 4).
        """

        # In RPN Heads, only the last feature map of backbone is used.
        # And body_feat_names[-1] represents the last level name of backbone.
        body_feat = list(body_feats.values())[-1]
        rpn_cls_score, rpn_bbox_pred = self._get_output(body_feat)

        if self.num_classes == 1:
            rpn_cls_prob = fluid.layers.sigmoid(
                rpn_cls_score, name='rpn_cls_prob')
        else:
            rpn_cls_score = fluid.layers.transpose(
                rpn_cls_score, perm=[0, 2, 3, 1])
            rpn_cls_score = fluid.layers.reshape(
                rpn_cls_score, shape=(0, 0, 0, -1, self.num_classes))
            rpn_cls_prob_tmp = fluid.layers.softmax(
                rpn_cls_score, use_cudnn=False, name='rpn_cls_prob')
            rpn_cls_prob_slice = fluid.layers.slice(
                rpn_cls_prob_tmp,
                axes=[4],
                starts=[1],
                ends=[self.num_classes])
            rpn_cls_prob, _ = fluid.layers.topk(rpn_cls_prob_slice, 1)
            rpn_cls_prob = fluid.layers.reshape(
                rpn_cls_prob, shape=(0, 0, 0, -1))
            rpn_cls_prob = fluid.layers.transpose(
                rpn_cls_prob, perm=[0, 3, 1, 2])
        if mode == 'train':
            rpn_rois, rpn_roi_probs = fluid.layers.generate_proposals(
                scores=rpn_cls_prob,
                bbox_deltas=rpn_bbox_pred,
                im_info=im_info,
                anchors=self.anchor,
                variances=self.anchor_var,
                pre_nms_top_n=self.train_pre_nms_top_n,
                post_nms_top_n=self.train_post_nms_top_n,
                nms_thresh=self.train_nms_thresh,
                min_size=self.train_min_size,
                eta=self.train_eta)
        else:
            rpn_rois, rpn_roi_probs = fluid.layers.generate_proposals(
                scores=rpn_cls_prob,
                bbox_deltas=rpn_bbox_pred,
                im_info=im_info,
                anchors=self.anchor,
                variances=self.anchor_var,
                pre_nms_top_n=self.test_pre_nms_top_n,
                post_nms_top_n=self.test_post_nms_top_n,
                nms_thresh=self.test_nms_thresh,
                min_size=self.test_min_size,
                eta=self.test_eta)
        return rpn_rois

    def _transform_input(self, rpn_cls_score, rpn_bbox_pred, anchor,
                         anchor_var):
        rpn_cls_score = fluid.layers.transpose(
            rpn_cls_score, perm=[0, 2, 3, 1])
        rpn_bbox_pred = fluid.layers.transpose(
            rpn_bbox_pred, perm=[0, 2, 3, 1])
        anchor = fluid.layers.reshape(anchor, shape=(-1, 4))
        anchor_var = fluid.layers.reshape(anchor_var, shape=(-1, 4))
        rpn_cls_score = fluid.layers.reshape(
            x=rpn_cls_score, shape=(0, -1, self.num_classes))
        rpn_bbox_pred = fluid.layers.reshape(x=rpn_bbox_pred, shape=(0, -1, 4))
        return rpn_cls_score, rpn_bbox_pred, anchor, anchor_var

    def _get_loss_input(self):
        for attr in ['rpn_cls_score', 'rpn_bbox_pred', 'anchor', 'anchor_var']:
            if not getattr(self, attr, None):
                raise ValueError("self.{} should not be None,".format(attr),
                                 "call RPNHead.get_proposals first")
        return self._transform_input(self.rpn_cls_score, self.rpn_bbox_pred,
                                     self.anchor, self.anchor_var)

    def get_loss(self, im_info, gt_box, is_crowd, gt_label=None):
        """
        Sample proposals and Calculate rpn loss.

        Args:
            im_info(Variable): The information of image with shape [N, 3] with
                shape (height, width, scale).
            gt_box(Variable): The ground-truth bounding boxes with shape [M, 4].
                M is the number of groundtruth.
            is_crowd(Variable): Indicates groud-truth is crowd or not with
                shape [M, 1]. M is the number of groundtruth.

        Returns:
            Type: dict
                rpn_cls_loss(Variable): RPN classification loss.
                rpn_bbox_loss(Variable): RPN bounding box regression loss.

        """
        rpn_cls, rpn_bbox, anchor, anchor_var = self._get_loss_input()
        if self.num_classes == 1:
            score_pred, loc_pred, score_tgt, loc_tgt, bbox_weight = \
                    fluid.layers.rpn_target_assign(
                        bbox_pred=rpn_bbox,
                        cls_logits=rpn_cls,
                        anchor_box=anchor,
                        anchor_var=anchor_var,
                        gt_boxes=gt_box,
                        is_crowd=is_crowd,
                        im_info=im_info,
                        rpn_batch_size_per_im=self.rpn_batch_size_per_im,
                        rpn_straddle_thresh=self.rpn_straddle_thresh,
                        rpn_fg_fraction=self.rpn_fg_fraction,
                        rpn_positive_overlap=self.rpn_positive_overlap,
                        rpn_negative_overlap=self.rpn_negative_overlap,
                        use_random=self.use_random)
            if self.rpn_cls_loss == 'SigmoidCrossEntropy':
                score_tgt = fluid.layers.cast(x=score_tgt, dtype='float32')
                score_tgt.stop_gradient = True
                rpn_cls_loss = fluid.layers.sigmoid_cross_entropy_with_logits(
                    x=score_pred, label=score_tgt)
            elif self.rpn_cls_loss == 'SigmoidFocalLoss':
                data = fluid.layers.fill_constant(
                    shape=[1], value=1, dtype='int32')
                fg_label = fluid.layers.greater_equal(score_tgt, data)
                fg_label = fluid.layers.cast(fg_label, dtype='int32')
                fg_num = fluid.layers.reduce_sum(fg_label)
                fg_num.stop_gradient = True
                score_tgt = fluid.layers.cast(x=score_tgt, dtype='float32')
                score_tgt.stop_gradient = True
                loss = fluid.layers.sigmoid_cross_entropy_with_logits(
                    x=score_pred, label=score_tgt)

                pred = fluid.layers.sigmoid(score_pred)
                p_t = pred * score_tgt + (1 - pred) * (1 - score_tgt)

                if self.rpn_focal_loss_alpha is not None:
                    alpha_t = self.rpn_focal_loss_alpha * score_tgt + (
                        1 - self.rpn_focal_loss_alpha) * (1 - score_tgt)
                    loss = alpha_t * loss
                gamma_t = fluid.layers.pow((1 - p_t),
                                           self.rpn_focal_loss_gamma)
                loss = gamma_t * loss
                rpn_cls_loss = loss / fg_num
        else:
            score_pred, loc_pred, score_tgt, loc_tgt, bbox_weight = \
                fluid.layers.rpn_target_assign(
                    bbox_pred=rpn_bbox,
                    cls_logits=rpn_cls,
                    anchor_box=anchor,
                    anchor_var=anchor_var,
                    gt_boxes=gt_box,
                    gt_labels=gt_label,
                    is_crowd=is_crowd,
                    num_classes=self.num_classes,
                    im_info=im_info,
                    rpn_batch_size_per_im=self.rpn_batch_size_per_im,
                    rpn_straddle_thresh=self.rpn_straddle_thresh,
                    rpn_fg_fraction=self.rpn_fg_fraction,
                    rpn_positive_overlap=self.rpn_positive_overlap,
                    rpn_negative_overlap=self.rpn_negative_overlap,
                    use_random=self.use_random)
            labels_int64 = fluid.layers.cast(x=score_tgt, dtype='int64')
            labels_int64.stop_gradient = True
            rpn_cls_loss = fluid.layers.softmax_with_cross_entropy(
                logits=score_pred,
                label=labels_int64,
                numeric_stable_mode=True)

        if self.rpn_cls_loss == 'SigmoidCrossEntropy':
            rpn_cls_loss = fluid.layers.reduce_mean(
                rpn_cls_loss, name='loss_rpn_cls')
        elif self.rpn_cls_loss == 'SigmoidFocalLoss':
            rpn_cls_loss = fluid.layers.reduce_sum(
                rpn_cls_loss, name='loss_rpn_cls')

        loc_tgt = fluid.layers.cast(x=loc_tgt, dtype='float32')
        loc_tgt.stop_gradient = True
        rpn_reg_loss = fluid.layers.smooth_l1(
            x=loc_pred,
            y=loc_tgt,
            sigma=3.0,
            inside_weight=bbox_weight,
            outside_weight=bbox_weight)
        rpn_reg_loss = fluid.layers.reduce_sum(
            rpn_reg_loss, name='loss_rpn_bbox')
        if self.rpn_cls_loss == 'SigmoidCrossEntropy':
            score_shape = fluid.layers.shape(score_tgt)
            score_shape = fluid.layers.cast(x=score_shape, dtype='float32')
            norm = fluid.layers.reduce_prod(score_shape)
            norm.stop_gradient = True
            rpn_reg_loss = rpn_reg_loss / norm
        elif self.rpn_cls_loss == 'SigmoidFocalLoss':
            rpn_reg_loss = rpn_reg_loss / fluid.layers.cast(fg_num,
                                                            rpn_reg_loss.dtype)
        return {'loss_rpn_cls': rpn_cls_loss, 'loss_rpn_bbox': rpn_reg_loss}


class FPNRPNHead(RPNHead):
    def __init__(
            self,
            anchor_start_size=32,
            aspect_ratios=[0.5, 1., 2.],
            variance=[1., 1., 1., 1.],
            num_chan=256,
            min_level=2,
            max_level=6,
            #rpn_target_assign
            rpn_batch_size_per_im=256,
            rpn_straddle_thresh=0.,
            rpn_fg_fraction=0.5,
            rpn_positive_overlap=0.7,
            rpn_negative_overlap=0.3,
            use_random=True,
            rpn_cls_loss='SigmoidCrossEntropy',
            rpn_focal_loss_gamma=2,
            rpn_focal_loss_alpha=0.25,
            #train_proposal
            train_pre_nms_top_n=2000,
            train_post_nms_top_n=2000,
            train_nms_thresh=.7,
            train_min_size=.0,
            train_eta=1.,
            #test_proposal
            test_pre_nms_top_n=1000,
            test_post_nms_top_n=1000,
            test_nms_thresh=.7,
            test_min_size=.0,
            test_eta=1.,
            #num_classes
            num_classes=1):
        super(FPNRPNHead, self).__init__(
            aspect_ratios=aspect_ratios,
            variance=variance,
            rpn_batch_size_per_im=rpn_batch_size_per_im,
            rpn_straddle_thresh=rpn_straddle_thresh,
            rpn_fg_fraction=rpn_fg_fraction,
            rpn_positive_overlap=rpn_positive_overlap,
            rpn_negative_overlap=rpn_negative_overlap,
            use_random=use_random,
            train_pre_nms_top_n=train_pre_nms_top_n,
            train_post_nms_top_n=train_post_nms_top_n,
            train_nms_thresh=train_nms_thresh,
            train_min_size=train_min_size,
            train_eta=train_eta,
            test_pre_nms_top_n=test_pre_nms_top_n,
            test_post_nms_top_n=test_post_nms_top_n,
            test_nms_thresh=test_nms_thresh,
            test_min_size=test_min_size,
            test_eta=test_eta,
            num_classes=num_classes,
            rpn_cls_loss=rpn_cls_loss,
            rpn_focal_loss_gamma=rpn_focal_loss_gamma,
            rpn_focal_loss_alpha=rpn_focal_loss_alpha)
        self.anchor_start_size = anchor_start_size
        self.num_chan = num_chan
        self.min_level = min_level
        self.max_level = max_level
        self.num_classes = num_classes

        self.fpn_rpn_list = []
        self.anchors_list = []
        self.anchor_var_list = []

    def _get_output(self, input, feat_lvl):
        """
        Get anchor and FPN RPN head output at one level.

        Args:
            input(Variable): Body feature from backbone.
            feat_lvl(int): Indicate the level of rpn output corresponding
                to the level of feature map.

        Return:
            rpn_cls_score(Variable): Output of one level of fpn rpn head with
                shape of [N, num_anchors, H, W].
            rpn_bbox_pred(Variable): Output of one level of fpn rpn head with
                shape of [N, num_anchors * 4, H, W].
        """
        slvl = str(feat_lvl)
        conv_name = 'conv_rpn_fpn' + slvl
        cls_name = 'rpn_cls_logits_fpn' + slvl
        bbox_name = 'rpn_bbox_pred_fpn' + slvl
        conv_share_name = 'conv_rpn_fpn' + str(self.min_level)
        cls_share_name = 'rpn_cls_logits_fpn' + str(self.min_level)
        bbox_share_name = 'rpn_bbox_pred_fpn' + str(self.min_level)

        num_anchors = len(self.aspect_ratios)
        conv_rpn_fpn = fluid.layers.conv2d(
            input=input,
            num_filters=self.num_chan,
            filter_size=3,
            padding=1,
            act='relu',
            name=conv_name,
            param_attr=ParamAttr(
                name=conv_share_name + '_w',
                initializer=Normal(
                    loc=0., scale=0.01)),
            bias_attr=ParamAttr(
                name=conv_share_name + '_b',
                learning_rate=2.,
                regularizer=L2Decay(0.)))

        self.anchors, self.anchor_var = fluid.layers.anchor_generator(
            input=conv_rpn_fpn,
            anchor_sizes=(self.anchor_start_size * 2.
                          **(feat_lvl - self.min_level), ),
            stride=(2.**feat_lvl, 2.**feat_lvl),
            aspect_ratios=self.aspect_ratios,
            variance=self.variance)

        cls_num_filters = num_anchors * self.num_classes
        if self.rpn_cls_loss == 'SigmoidCrossEntropy':
            bias_init = None
        elif self.rpn_cls_loss == 'SigmoidFocalLoss':
            value = float(-np.log((1 - 0.01) / 0.01))
            bias_init = Constant(value=value)
        self.rpn_cls_score = fluid.layers.conv2d(
            input=conv_rpn_fpn,
            num_filters=cls_num_filters,
            filter_size=1,
            act=None,
            name=cls_name,
            param_attr=ParamAttr(
                name=cls_share_name + '_w',
                initializer=Normal(
                    loc=0., scale=0.01)),
            bias_attr=ParamAttr(
                name=cls_share_name + '_b',
                initializer=bias_init,
                learning_rate=2.,
                regularizer=L2Decay(0.)))
        self.rpn_bbox_pred = fluid.layers.conv2d(
            input=conv_rpn_fpn,
            num_filters=num_anchors * 4,
            filter_size=1,
            act=None,
            name=bbox_name,
            param_attr=ParamAttr(
                name=bbox_share_name + '_w',
                initializer=Normal(
                    loc=0., scale=0.01)),
            bias_attr=ParamAttr(
                name=bbox_share_name + '_b',
                learning_rate=2.,
                regularizer=L2Decay(0.)))
        return self.rpn_cls_score, self.rpn_bbox_pred

    def _get_single_proposals(self, body_feat, im_info, feat_lvl,
                              mode='train'):
        """
        Get proposals in one level according to the output of fpn rpn head

        Args:
            body_feat(Variable): the feature map from backone.
            im_info(Variable): The information of image with shape [N, 3] with
                format (height, width, scale).
            feat_lvl(int): Indicate the level of proposals corresponding to
                the feature maps.

        Returns:
            rpn_rois_fpn(Variable): Output proposals with shape of (rois_num, 4).
            rpn_roi_probs_fpn(Variable): Scores of proposals with
                shape of (rois_num, 1).
        """

        rpn_cls_score_fpn, rpn_bbox_pred_fpn = self._get_output(body_feat,
                                                                feat_lvl)

        if self.num_classes == 1:
            rpn_cls_prob_fpn = fluid.layers.sigmoid(
                rpn_cls_score_fpn, name='rpn_cls_prob_fpn' + str(feat_lvl))
        else:
            rpn_cls_score_fpn = fluid.layers.transpose(
                rpn_cls_score_fpn, perm=[0, 2, 3, 1])
            rpn_cls_score_fpn = fluid.layers.reshape(
                rpn_cls_score_fpn, shape=(0, 0, 0, -1, self.num_classes))
            rpn_cls_prob_fpn = fluid.layers.softmax(
                rpn_cls_score_fpn,
                use_cudnn=False,
                name='rpn_cls_prob_fpn' + str(feat_lvl))
            rpn_cls_prob_fpn = fluid.layers.slice(
                rpn_cls_prob_fpn,
                axes=[4],
                starts=[1],
                ends=[self.num_classes])
            rpn_cls_prob_fpn, _ = fluid.layers.topk(rpn_cls_prob_fpn, 1)
            rpn_cls_prob_fpn = fluid.layers.reshape(
                rpn_cls_prob_fpn, shape=(0, 0, 0, -1))
            rpn_cls_prob_fpn = fluid.layers.transpose(
                rpn_cls_prob_fpn, perm=[0, 3, 1, 2])

        if mode == 'train':
            rpn_rois_fpn, rpn_roi_prob_fpn = fluid.layers.generate_proposals(
                scores=rpn_cls_prob_fpn,
                bbox_deltas=rpn_bbox_pred_fpn,
                im_info=im_info,
                anchors=self.anchors,
                variances=self.anchor_var,
                pre_nms_top_n=self.train_pre_nms_top_n,
                post_nms_top_n=self.train_post_nms_top_n,
                nms_thresh=self.train_nms_thresh,
                min_size=self.train_min_size,
                eta=self.train_eta)
        else:
            rpn_rois_fpn, rpn_roi_prob_fpn = fluid.layers.generate_proposals(
                scores=rpn_cls_prob_fpn,
                bbox_deltas=rpn_bbox_pred_fpn,
                im_info=im_info,
                anchors=self.anchors,
                variances=self.anchor_var,
                pre_nms_top_n=self.test_pre_nms_top_n,
                post_nms_top_n=self.test_post_nms_top_n,
                nms_thresh=self.test_nms_thresh,
                min_size=self.test_min_size,
                eta=self.test_eta)

        return rpn_rois_fpn, rpn_roi_prob_fpn

    def get_proposals(self, fpn_feats, im_info, mode='train'):
        """
        Get proposals in multiple levels according to the output of fpn
        rpn head

        Args:
            fpn_feats(dict): A dictionary represents the output feature map
                of FPN with their name.
            im_info(Variable): The information of image with shape [N, 3] with
                format (height, width, scale).

        Return:
            rois_list(Variable): Output proposals in shape of [rois_num, 4]
        """
        rois_list = []
        roi_probs_list = []
        fpn_feat_names = list(fpn_feats.keys())
        for lvl in range(self.min_level, self.max_level + 1):
            fpn_feat_name = fpn_feat_names[self.max_level - lvl]
            fpn_feat = fpn_feats[fpn_feat_name]
            rois_fpn, roi_probs_fpn = self._get_single_proposals(
                fpn_feat, im_info, lvl, mode)
            self.fpn_rpn_list.append((self.rpn_cls_score, self.rpn_bbox_pred))
            rois_list.append(rois_fpn)
            roi_probs_list.append(roi_probs_fpn)
            self.anchors_list.append(self.anchors)
            self.anchor_var_list.append(self.anchor_var)
        post_nms_top_n = self.train_post_nms_top_n if mode == 'train' else \
            self.test_post_nms_top_n
        rois_collect = fluid.layers.collect_fpn_proposals(
            rois_list,
            roi_probs_list,
            self.min_level,
            self.max_level,
            post_nms_top_n,
            name='collect')
        return rois_collect

    def _get_loss_input(self):
        rpn_clses = []
        rpn_bboxes = []
        anchors = []
        anchor_vars = []
        for i in range(len(self.fpn_rpn_list)):
            single_input = self._transform_input(
                self.fpn_rpn_list[i][0], self.fpn_rpn_list[i][1],
                self.anchors_list[i], self.anchor_var_list[i])
            rpn_clses.append(single_input[0])
            rpn_bboxes.append(single_input[1])
            anchors.append(single_input[2])
            anchor_vars.append(single_input[3])

        rpn_cls = fluid.layers.concat(rpn_clses, axis=1)
        rpn_bbox = fluid.layers.concat(rpn_bboxes, axis=1)
        anchors = fluid.layers.concat(anchors)
        anchor_var = fluid.layers.concat(anchor_vars)
        return rpn_cls, rpn_bbox, anchors, anchor_var
