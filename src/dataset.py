import scipy
import numpy as np
from tensorflow.examples.tutorials.mnist import input_data
from utils import *
from glob import glob
from utils_image import *

project_path = ProjectPath("log")


class DataSet:
    """
    Abstract class that WGAN uses, needs to have a method which returns samples from the data
    """

    def next_batch_real(self, batch_size):
        """

        :param batch_size:
        :return: Tensor of real images in the shape [batch_size, height, width, channels]
        """
        raise NotImplementedError()

    def next_batch_fake(self, batch_size, z_size):
        return np.random.rand(batch_size, z_size)


class MNISTData(DataSet):
    def __init__(self):
        self.mnist = input_data.read_data_sets("MNIST_data/", reshape=False, one_hot=True)
        self.img_size = 28
        self.channels = 1

    def next_batch_real(self, batch_size):
        images, labels = self.mnist.train.next_batch(batch_size)
        return images


class FacesData(DataSet):
    def __init__(self, img_size, crop_size=128):
        """
        Faces dataset from the Labeled Faces in the Wild dataset, the deepfunelled version.
        Images are first cropped, then resized to the desired size.

        :param img_size: size to which resize the images to
        :param crop_size:
        """
        assert img_size <= crop_size <= 250
        self.img_size = img_size
        self.channels = 3
        self.crop_size = crop_size
        images_folder_path = os.path.join(project_path.base, "data", "lfw-deepfunneled")
        self.images_path = []
        for (dirpath, dirnames, fnames) in os.walk(images_folder_path):
            for fname in fnames:
                self.images_path.append(os.path.join(dirpath, fname))
        # training only on 2000 images for now, for speed and memory reasons
        self.images_path = self.images_path[:2000]
        self.num_examples = len(self.images_path)
        self.images = np.zeros((len(self.images_path), self.img_size, self.img_size, 3))

        print("Loading dataset...")
        for i, img_path in enumerate(self.images_path):
            if i % 1000 == 0:
                print(i, "/", len(self.images_path))
            self.images[i] = self.get_image(img_path, resize_dim=self.img_size)
        print("Done")

    def next_batch_real(self, size):
        locations = np.random.randint(0, self.num_examples, size)
        return self.images[locations, ...]

    def get_image(self, path, resize_dim=None):
        img = FacesData.read_image(path)
        img = FacesData.center_crop(img, crop_h=self.crop_size)
        if resize_dim is not None:
            rev_rat = self.crop_size / resize_dim  # ratio
            assert rev_rat.is_integer()
            rev_rat = int(rev_rat)
            img = img[::rev_rat, ::rev_rat]
        return img

    @staticmethod
    def read_image(path):
        # dividing with 256 because we need to get it in the [0, 1] range
        return scipy.misc.imread(path).astype(np.float) / 256

    @staticmethod
    def center_crop(x, crop_h, crop_w=None):
        if crop_w is None:
            crop_w = crop_h
        h, w = x.shape[:2]
        j = round((h - crop_h) / 2)
        i = round((w - crop_w) / 2)
        return x[j:j + crop_h, i:i + crop_w]


class CelebAData(DataSet):
    def __init__(self, img_size, dataset_size, input_height = 108, input_width = 108):
        self.attributes = []
        self.img_attributes = []
        self.input_height = input_height  # 108
        self.input_width = input_width  # 108
        self.img_size = img_size  # 64
        self.channels = 3
        self.idx = 0
        self.dataset_size = dataset_size
        print('Loading images data...')
        self.data = glob(os.path.join("data", "celebA", '*.jpg'))
        # Limit dataset size
        if dataset_size > 0:
            self.data = self.data[:dataset_size]
        else:
            self.dataset_size = len(self.data)
        print('Loading images data completed.')
        # print('Resizing images...')
        # print('Resizing images completed.')
        # self.images = np.array(files).astype(np.float32)

    def load_attributes(self):
        print('Loading attributes...')
        list_attr_file = 'list_attr_celeba.txt'
        with open(list_attr_file) as f:
            n = int(f.readline())
            self.attributes = f.readline().split()
            for _ in range(0, n):
                parts = f.readline().split()
                attrs = [int(x) for x in parts[1:]]
                self.img_attributes.append(attrs)
        print('Loading attributes completed.')

    def next_batch_real(self, batch_size):
        ret = []
        for _ in range(0, batch_size):
            ret.append(get_image(self.data[self.idx],
                                 input_height = self.input_height,
                                 input_width = self.input_width,
                                 resize_height = self.img_size,
                                 resize_width = self.img_size,
                                 crop = True,
                                 grayscale = False))
            self.idx += 1
            if self.idx == self.dataset_size:
                self.idx = 0
        return ret

    def get_img_by_idx(self, idx):
        return get_image(self.data[idx],
                         input_height=self.input_height,
                         input_width=self.input_width,
                         resize_height=self.img_size,
                         resize_width=self.img_size,
                         crop=True,
                         grayscale=False)

    def get_images_batch(self, st, batch_size):
        ret = []
        for i in range(st, st + batch_size):
            if i >= self.dataset_size:
                break
            ret.append(get_image(self.data[i],
                                 input_height = self.input_height,
                                 input_width = self.input_width,
                                 resize_height = self.img_size,
                                 resize_width = self.img_size,
                                 crop = True,
                                 grayscale = False))
        return ret

    def get_nearest_neighbor(self, images):
        print('Searching for nearest neighbor...')
        nearest = np.zeros(images.shape)
        nearest_dist = np.zeros(images.shape[0])
        nearest_idx = np.zeros(images.shape[0])
        nearest_dist.fill(-1)
        for i in range(self.dataset_size):
            sample = get_image(self.data[i],
                               input_height = self.input_height,
                               input_width = self.input_width,
                               resize_height = self.img_size,
                               resize_width = self.img_size,
                               crop = True,
                               grayscale = False)
            for idx, img in enumerate(images):
                d = image_distance(img, sample)
                if nearest_dist[idx] < 0 or d < nearest_dist[idx]:
                    nearest_dist[idx] = d
                    nearest[idx] = sample
            print('{} / {}'.format(i, self.dataset_size))
        return nearest

