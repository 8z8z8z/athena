# coding=utf-8
# Copyright (C) 2019 ATHENA AUTHORS; Xiangang Li; Jianwei Sun; Ruixiong Zhang
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
# ==============================================================================
# pylint: disable=arguments-differ
# pylint: disable=no-member
"""Base class for cross entropy model."""

import warnings
import time
import tensorflow as tf
from absl import logging
from .utils.hparam import register_and_parse_hparams
from .utils.metric_check import MetricChecker
from .utils.misc import validate_seqs
from .metrics import CharactorAccuracy


class BaseSolver(tf.keras.Model):
    """Base Solver.
    """
    default_config = {
        "clip_norm": 100.0,
        "log_interval": 10,
        "enable_tf_function": True
    }
    def __init__(self, model, optimizer, sample_signature, config=None, **kwargs):
        super().__init__(**kwargs)
        self.model = model
        self.optimizer = optimizer
        self.metric_checker = MetricChecker(self.optimizer)
        self.sample_signature = sample_signature
        self.hparams = register_and_parse_hparams(self.default_config, config, cls=self.__class__)

    @staticmethod
    def initialize_devices(visible_gpu_idx=None):
        """ initialize hvd devices, should be called firstly """
        gpus = tf.config.experimental.list_physical_devices("GPU")
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
        # means we're running in GPU mode
        if len(gpus) != 0:
            assert len(gpus) >= len(visible_gpu_idx)
            for idx in visible_gpu_idx:
                tf.config.experimental.set_visible_devices(gpus[idx], "GPU")

    @staticmethod
    def clip_by_norm(grads, norm):
        """ clip norm using tf.clip_by_norm """
        if norm <= 0:
            return grads
        grads = [
            None if gradient is None else tf.clip_by_norm(gradient, norm)
            for gradient in grads
        ]
        return grads

    def train_step(self, samples):
        """ train the model 1 step """
        with tf.GradientTape() as tape:
            logits = self.model(samples, training=True)
            loss, metrics = self.model.get_loss(logits, samples, training=True)
        grads = tape.gradient(loss, self.model.trainable_variables)
        grads = self.clip_by_norm(grads, self.hparams.clip_norm)
        self.optimizer.apply_gradients(zip(grads, self.model.trainable_variables))
        return loss, metrics

    def train(self, dataset, total_batches=-1):
        """ Update the model in 1 epoch """
        train_step = self.train_step
        if self.hparams.enable_tf_function:
            logging.info("please be patient, enable tf.function, it takes time ...")
            train_step = tf.function(train_step, input_signature=self.sample_signature)
        train_start = time.time()
        for batch, samples in enumerate(dataset.take(total_batches)):
            # train 1 step
            samples = self.model.prepare_samples(samples)
            step_time_start = time.time()
            loss, metrics = train_step(samples)
            #with self.summary_writer.as_default():
            #    tf.summary.trace_export(name="model_trace", step=0, profiler_outdir=self.p.summary_dir + 'log')
            if batch % self.hparams.log_interval == 0:
                logging.info(self.metric_checker(loss, metrics))
                self.model.reset_metrics()
            step_time_end = time.time()
            train_end = time.time()
            train_time = train_end - train_start
            step_time = step_time_end - step_time_start
            data_read_time = step_time_start - train_start
            logging.info("train_time: "+str(train_time))
            logging.info("step_time: " + str(step_time))
            logging.info("data_read_time: "+str(data_read_time))

    def evaluate_step(self, samples):
        """ evaluate the model 1 step """
        logits = self.model(samples, training=False)
        loss, metrics = self.model.get_loss(logits, samples, training=False)
        return loss, metrics

    def evaluate(self, dataset, epoch):
        """ evaluate the model """
        loss_metric = tf.keras.metrics.Mean(name="AverageLoss")
        loss, metrics = None, None
        evaluate_step = self.evaluate_step
        if self.hparams.enable_tf_function:
            logging.info("please be patient, enable tf.function, it takes time ...")
            evaluate_step = tf.function(evaluate_step, input_signature=self.sample_signature)
        self.model.reset_metrics()  # init metric.result() with 0
        for batch, samples in enumerate(dataset):
            samples = self.model.prepare_samples(samples)
            loss, metrics = evaluate_step(samples)
            if batch % self.hparams.log_interval == 0:
                logging.info(self.metric_checker(loss, metrics, -2))
            loss_metric.update_state(loss)
        logging.info(self.metric_checker(loss_metric.result(), metrics, evaluate_epoch=epoch))
        self.model.reset_metrics()
        return loss_metric.result()

class BaseSolverSummary(tf.keras.Model):
    """Base Solver.
    """
    default_config = {
        "clip_norm": 100.0,
        "log_interval": 10,
        "enable_tf_function": True
    }
    def __init__(self, model, optimizer, sample_signature, config=None, **kwargs):
        super().__init__(**kwargs)
        self.model = model
        self.optimizer = optimizer
        self.metric_checker = MetricChecker(self.optimizer)
        self.sample_signature = sample_signature
        self.hparams = register_and_parse_hparams(self.default_config, config, cls=self.__class__)

    @staticmethod
    def initialize_devices(visible_gpu_idx=None):
        """ initialize hvd devices, should be called firstly """
        gpus = tf.config.experimental.list_physical_devices("GPU")
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
        # means we're running in GPU mode
        if len(gpus) != 0:
            assert len(gpus) >= len(visible_gpu_idx)
            for idx in visible_gpu_idx:
                tf.config.experimental.set_visible_devices(gpus[idx], "GPU")

    @staticmethod
    def clip_by_norm(grads, norm):
        """ clip norm using tf.clip_by_norm """
        if norm <= 0:
            return grads
        grads = [
            None if gradient is None else tf.clip_by_norm(gradient, norm)
            for gradient in grads
        ]
        return grads

    def train_step(self, samples):
        """ train the model 1 step """
        with tf.GradientTape() as tape:
            logits = self.model(samples, training=True)
            loss, metrics = self.model.get_loss(logits, samples, training=True)
        grads = tape.gradient(loss, self.model.trainable_variables)
        grads = self.clip_by_norm(grads, self.hparams.clip_norm)
        self.optimizer.apply_gradients(zip(grads, self.model.trainable_variables))
        return loss, metrics

    def train(self, dataset, total_batches=-1):
        """ Update the model in 1 epoch """
        train_step = self.train_step
        if self.hparams.enable_tf_function:
            logging.info("please be patient, enable tf.function, it takes time ...")
            train_step = tf.function(train_step, input_signature=self.sample_signature)
        for batch, samples in enumerate(dataset.take(total_batches)):
            # train 1 step
            samples = self.model.prepare_samples(samples)
            loss, metrics = train_step(samples)
            tf.summary.trace_export(name="model_trace", step=batch, profiler_outdir=self.summary_dir)
            if batch % self.hparams.log_interval == 0:
                logging.info(self.metric_checker(loss, metrics))
                self.model.reset_metrics()

    def evaluate_step(self, samples):
        """ evaluate the model 1 step """
        logits = self.model(samples, training=False)
        loss, metrics = self.model.get_loss(logits, samples, training=False)
        return loss, metrics

    def evaluate(self, dataset, epoch):
        """ evaluate the model """
        loss_metric = tf.keras.metrics.Mean(name="AverageLoss")
        loss, metrics = None, None
        evaluate_step = self.evaluate_step
        if self.hparams.enable_tf_function:
            logging.info("please be patient, enable tf.function, it takes time ...")
            evaluate_step = tf.function(evaluate_step, input_signature=self.sample_signature)
        self.model.reset_metrics()  # init metric.result() with 0
        for batch, samples in enumerate(dataset):
            samples = self.model.prepare_samples(samples)
            loss, metrics = evaluate_step(samples)
            if batch % self.hparams.log_interval == 0:
                logging.info(self.metric_checker(loss, metrics, -2))
            loss_metric.update_state(loss)
        logging.info(self.metric_checker(loss_metric.result(), metrics, evaluate_epoch=epoch))
        self.model.reset_metrics()
        return loss_metric.result()
    def summary(self, summary_dir):
        self.summary_dir = summary_dir
        #self.summary_writer = tf.summary.create_file_writer(summary_dir + 'log')
class DecoderSolver(BaseSolver):
    """ DecoderSolver
    """
    default_config = {
        "beam_search": True,
        "beam_size": 4,
        "ctc_weight": 0.0,
        "lm_weight": 0.1,
        "lm_type": "",
        "lm_path": None
    }

    # pylint: disable=super-init-not-called
    def __init__(self, model, config=None, lm_model=None):
        super().__init__(model, None, None)
        self.model = model
        self.hparams = register_and_parse_hparams(self.default_config, config, cls=self.__class__)
        self.lm_model = lm_model

    def decode(self, dataset):
        """ decode the model """
        if dataset is None:
            return
        metric = CharactorAccuracy()
        for _, samples in enumerate(dataset):
            begin = time.time()
            samples = self.model.prepare_samples(samples)
            predictions = self.model.decode(samples, self.hparams, lm_model=self.lm_model)
            validated_preds = validate_seqs(predictions, self.model.eos)[0]
            validated_preds = tf.cast(validated_preds, tf.int64)
            num_errs, _ = metric.update_state(validated_preds, samples)
            reports = (
                "predictions: %s\tlabels: %s\terrs: %d\tavg_acc: %.4f\tsec/iter: %.4f"
                % (
                    predictions,
                    samples["output"].numpy(),
                    num_errs,
                    metric.result(),
                    time.time() - begin,
                )
            )
            logging.info(reports)
        logging.info("decoding finished")
