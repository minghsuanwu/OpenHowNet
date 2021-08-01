import os
import pickle
import sys
from typing import Dict, Any

from anytree import Node, RenderTree
from anytree.exporter import DictExporter, JsonExporter

from OpenHowNet.SememeTreeParser import GenSememeTree
from OpenHowNet.pack.submit_user import util
from OpenHowNet.pack.submit_user.main import sense_similarity, word_similarity

from OpenHowNet.Download import get_resource


class Sememe(object):
    """Sememe class.

    The smallest semantic unit. Described in English and Chinese.

    Attributes:
        en: English word to describe the sememe.
        ch: Chinese word to describe the sememe.
        freq: the sememe occurence frequency in HowNet.
        related_sememes_forward: the sememes related with the sememe in HowNet and the sememe is head sememe in triples.
        related_sememes_backward: the sememes related with the sememe in HowNet and the sememe is tail sememe in triples.
    """

    def __init__(self, hownet_sememe, freq):
        """Initialize a sememe by sememe annotations.

        :param hownet_sememe: sememe annotiation in HowNet.
        :param freq: sememe occurence freqency.
        """
        self.en, self.ch = hownet_sememe.split('|')
        self.en_ch = hownet_sememe
        self.freq = freq
        self.related_sememes_forward = {}
        self.related_sememes_backward = {}
        self.senses = []

    def __repr__(self):
        """
        Define how to print the sememe.
        """
        return self.en_ch

    def add_related_sememes_forward(self, head, relation, tail):
        """Add a sememe triple to the sememe.

        Sememe triple contains (head sememe, relation, tail sememe).
        """
        self.related_sememes_forward[relation] = tail

    def add_related_sememes_backward(self, head, relation, tail):
        """Add a sememe triple to the sememe.

        Sememe triple contains (head sememe, relation, tail sememe).
        """
        self.related_sememes_backward[relation] = head


class Sense(object):
    """Contains variables of a sense.

    Initialized by an item in HowNet.
    Contains numbering, word, POS of word, sememe tree, etc.

    Attributes:
        No: the id of the sense in HowNet.
        en_word: the word describing the sense in HowNet in English.
        en_grammar: the POS of the word in English.
        ch_word: the word describing the sense in HowNet in Chinese.
        ch_grammar: the POS of the word in Chinese.
        Def: the sememe tree of the sense.
    """

    def __init__(self, hownet_sense):
        """Initialize a sense object by a hownet item.

        Initialize the attributes of the sense.

        :param hownet_sense: (Dict)The Annotation of the sense in HowNet.
        """
        self.No = hownet_sense['No']
        self.en_word = hownet_sense['en_word']
        self.en_grammar = hownet_sense['en_grammar']
        self.ch_word = hownet_sense['ch_word']
        self.ch_grammar = hownet_sense['ch_grammar']
        self.Def = hownet_sense['Def']
        self.sememes = []

    def __repr__(self):
        """
        Define how to print the sense.
        """
        return self.No

    def get_sememes(self, display="list"):
        """Get the sememe annotiation of the sense.

        You can retrieve sememes of the sense in different display mode.

        :param display: (str)The display mode of sememes.
            You can choose from list/json/visual.
        :return: sememe list or sememe tree or sememe dict
        """
        pass


class HowNetDict(object):

    def __init__(self, use_sim=False):
        '''
        Initialize HowNetDict
        :param use_sim: "lazy" option for loading similarity computation file.
        '''
        try:
            package_directory = os.path.dirname(os.path.abspath(__file__))
            sememe_dir, sememe_triples_dir, data_dir = [os.path.join(package_directory, file_name) for file_name in [
                'sememe_all', 'sememe_triples_taxonomy.txt', 'HowNet_dict_complete']]

            # Initialize sememe list from sememe_all.
            self.sememe_dic = dict()
            with get_resource(sememe_dir, 'rb') as sememe_dict:
                sememe_all = pickle.load(sememe_dict)
            sememe_dict.close()
            for k, v in sememe_all.items():
                self.sememe_dic[k] = Sememe(k, v)
            sememe_triples = get_resource(sememe_triples_dir, "r")
            for line in sememe_triples.readlines():
                line = line.strip().split(" ")
                self.sememe_dic[line[0]].add_related_sememes_forward(
                    self.sememe_dic[line[0]], line[1], self.sememe_dic[line[2]])
                self.sememe_dic[line[2]].add_related_sememes_backward(
                    self.sememe_dic[line[0]], line[1], self.sememe_dic[line[2]])
            sememe_triples.close()

            # Initialize sense list from HowNet_dict_complete
            self.sense_dic = dict()
            with get_resource(data_dir, 'rb') as origin_dict:
                hownet_dict = pickle.load(origin_dict)
            origin_dict.close()
            for k, v in hownet_dict.items():
                self.sense_dic[k] = Sense(v)
                self.sense_dic[k].sememes = self._gen_sememe_list(
                    self.sense_dic[k])
                for s in self.sense_dic[k].sememes:
                    s.senses.append(self.sense_dic[k])

            # Initialize the sense dic to retrieve by word.
            self.en_map = dict()
            self.zh_map = dict()
            for k in self.sense_dic.keys():
                en_word = self.sense_dic[k].en_word.strip()
                zh_word = self.sense_dic[k].ch_word.strip()
                if en_word not in self.en_map:
                    self.en_map[en_word] = list()
                self.en_map[en_word].append(self.sense_dic[k])
                if zh_word not in self.zh_map:
                    self.zh_map[zh_word] = list()
                self.zh_map[zh_word].append(self.sense_dic[k])

            if use_sim:
                if not self.initialize_sememe_similarity_calculation():
                    self.hownet = None
                    self.sememe_root = None
                    self.sememe_sim_table = None
        except FileNotFoundError as e:
            print(e)

    def __getitem__(self, item):
        """
        Shortcut for Get(self,item,None)
        :param item: target word.
        :return:(List) candidates HowNet annotation, if the target word does not exist, return an empty list.
        """
        res = list()
        if item == "I WANT ALL!":
            for item in self.sense_dic.values():
                res.extend(item)
            return res
        if item in self.en_map:
            res.extend(self.en_map[item])
        if item in self.zh_map:
            res.extend(self.zh_map[item])
        if item in self.sense_dic:
            res.extend(self.sense_dic[item])
        return res

    def __len__(self):
        """
        Get the num of the concepts in HowNet.
        :return:(Int) the num of the concepts in HowNet.
        """
        return len(self.sense_dic)

    def get(self, word, language=None):
        """
        Common word search API, you can specify the language of the target word to boost the search performance
        :param word: target word
        :param language: target language, default: None
                (The func will search both in English and Chinese, which will consume a lot of time.)
        :return:(List) candidates HowNet annotation, if the target word does not exist, return an empty list.
        """
        res = list()
        if language == "en":
            if (word in self.en_map):
                res = self.en_map[word]
        elif language == "zh":
            if (word in self.zh_map):
                res = self.zh_map[word]
        else:
            res = self[word]
        return res

    def get_zh_words(self):
        """
        Get all Chinese words annotated in HowNet
        :return: (list) All annotated Chinese words in HowNet.
        """
        return list(self.zh_map.keys())

    def get_en_words(self):
        """
        Get all English words annotated in HowNet
        :return: (list) All annotated English words in HowNet.
        """
        return list(self.en_map.keys())

    def _gen_sememe_tree(self, sense, return_node=False):
        """Generate sememe tree for the sense by the Def.

        :param sense: the sense to generate sememe tree.
        :param return_node: (bool)whether to return as anttree node.
        :return :(Dict)the sememe tree of the sense.
        """
        kdml = sense.Def
        rmk_pos = kdml.find('RMK=')
        if rmk_pos >= 0:
            kdml = kdml[:rmk_pos]
        kdml_list = kdml.split(";")
        root = Node(sense, role='sense')
        for kdml in kdml_list:
            entity_idx = []  # 义原起止位置集合
            node = []  # 树的节点集合
            pointer = []  # idx of '~' cases
            for i in range(len(kdml)):
                if kdml[i] in ['~', '?', '$']:
                    if kdml[i] == '~':
                        pointer.append(len(node))
                    entity_idx.append([i, i + 1])
                    node.append(Node(kdml[i], role='None'))
                elif kdml[i] == '|':
                    start_idx = i
                    end_idx = i
                    while kdml[start_idx] not in ['{', '"']:
                        start_idx = start_idx - 1
                    while kdml[end_idx] not in ['}', ':', '"']:
                        end_idx = end_idx + 1
                    entity_idx.append([start_idx + 1, end_idx])
                    node.append(Node(
                        self.sememe_dic[kdml[start_idx + 1: end_idx].replace(' ', '_')], role='None'))
            for i in range(len(entity_idx)):
                cursor = entity_idx[i][0]
                left_brace = 0
                right_brace = 0
                quotation = 0
                # 找到当前义原所属的主义原位置
                while not (kdml[cursor] == ':' and ((quotation % 2 == 0 and left_brace == right_brace + 1) or
                                                    (quotation % 2 == 1 and left_brace == right_brace))):
                    if cursor == 0:
                        break
                    if kdml[cursor] == '{':
                        left_brace = left_brace + 1
                    elif kdml[cursor] == '}':
                        right_brace = right_brace + 1
                    elif kdml[cursor] == '"':
                        quotation = quotation + 1
                    cursor = cursor - 1
                parent_idx = -1
                for j in range(i - 1, -1, -1):  # 从当前位置往前找可以对应上的义原
                    if entity_idx[j][1] == cursor:
                        node[i].parent = node[j]
                        parent_idx = j
                        break
                if i != 0:
                    if parent_idx != -1:
                        right_range = entity_idx[parent_idx][1] - 1
                    else:
                        right_range = entity_idx[i - 1][1] - 1
                    role_begin_idx = -1
                    role_end_idx = -1
                    # 修改：在当前义原和父义原之间找
                    for j in range(entity_idx[i][0] - 1, right_range, -1):
                        if kdml[j] == '=':
                            role_end_idx = j
                        elif kdml[j] in [',', ':']:
                            role_begin_idx = j
                            break
                    if role_end_idx != -1:
                        node[i].role = kdml[role_begin_idx + 1: role_end_idx]
            for i in pointer:
                node[i].parent.role = node[i].role
                node[i].parent = None
            node[0].parent = root
            if not return_node:
                # 转化成dict形式
                # exporter = DictExporter()
                return DictExporter().export(root)
            else:
                return root

    def _gen_sememe_list(self, sense):
        """Get sememe list for the sense by the Def.

        :param sense: the sense to generate sememe tree.
        :return :(List)the sememe list of the sense.
        """
        kdml = sense.Def
        res = list()
        for i in range(len(kdml)):
            if kdml[i] == '|':
                start_idx = i
                end_idx = i
                while kdml[start_idx] not in ['{', '"']:
                    start_idx = start_idx - 1
                while kdml[end_idx] not in ['}', ':', '"']:
                    end_idx = end_idx + 1
                res.append(self.sememe_dic[kdml[start_idx + 1:end_idx]])
        return res

    def _expand_tree(self, tree, layer, isRoot=True):
        """
        Expand the sememe tree by iteration.
        :param tree: the sememe tree to expand.
        :param layer: the layer num to expand the tree.
        :return:(Set) the sememe set of the sememe tree.
        """
        res = set()
        if layer == 0:
            return res
        target = tree

        if isinstance(tree, dict):
            target = list()
            target.append(tree)
        for item in target:
            try:
                if not isRoot:
                    if item['name'] != '$' and item['name'] != '?':
                        res.add(item["name"])
                if "children" in item:
                    res |= self._expand_tree(
                        item["children"], layer - 1, isRoot=False)
            except Exception as e:
                if isinstance(e, IndexError):
                    continue
                raise e
        return res

    def _visualize_sememe_trees(self, sense):
        """Visualize the sememe tree by sense Def.

        :param sense: The sense the visualized sememe tree belongs to.  
        :return:
        """
        tree = self._gen_sememe_tree(sense, return_node=True)
        tree = RenderTree(tree)
        for pre, fill, node in tree:
            print("%s[%s]%s" % (pre, node.role, node.name))

    def get_sememes_by_word(self, word, display='dict', merge=False, expanded_layer=-1, K=None):
        """
        Given specific word, you can get corresponding HowNet annotation.
        :param word: (str)specific word(en/zh/id) you want to search in HowNet.
                      You can use "I WANT ALL" or "*" to specify that you need annotations of all words.
        :param display: (str)how to display the sememes you retrieved, you can choose from tree/dict/list/visual.
        :param merge: (boolean)only works when display == 'list'. Decide whether to merge multi-sense word query results into one
        :param expanded_layer: (int)only works when display == 'list'. Continously expand k layer.
                                By default, it will be set to -1 (expand full layers)
        :param K: (int)only works when display == 'visual'.The maximum number of visualized words, ordered by id (ascending).
                                Illegal number will be automatically ignored and the function will display all retrieved results.
        :return: list of converted sememe trees in accordance with requirements specified by the params
        """
        queryResult = self[word]
        queryResult.sort(key=lambda x: x.No)
        result = set() if merge else list()
        if display == 'dict' or display == 'tree':
            for item in queryResult:
                try:
                    result.append(self._gen_sememe_tree(
                        item, return_node=display == 'tree'))
                except Exception as e:
                    print("Generate Sememe Tree Failed for", item.No)
                    print("Exception:", e)
                    continue
        elif display == 'list':
            for item in queryResult:
                try:
                    if not merge:
                        result.append(
                            {"sense": item,
                             "sememes": self._expand_tree(self._gen_sememe_tree(item), expanded_layer)})
                    else:
                        result |= set(self._expand_tree(
                            self._gen_sememe_tree(item), expanded_layer))
                except Exception as e:
                    print(word)
                    print("Wrong Item:", item)
                    print("Exception:", e)
                    raise e
        elif display == 'visual':
            print("Find {0} result(s)".format(len(queryResult)))
            if K is not None and K >= 1 and type(K) == int:
                queryResult = queryResult[:K]
            for index, item in enumerate(queryResult):
                print("Display #{0} sememe tree".format(index))
                self._visualize_sememe_trees(item)
        else:
            print("Wrong display mode: ", display)
        return result

    def __str__(self):
        return str(type(self))

    def has(self, item, language=None):
        """
        Check that whether certain word(English Word/Chinese Word/ID) exist in HowNet
        Only perform exact match because HowNet is case-sensitive
        By default, it will search the target word in both the English vocabulary and the Chinese vocabulary
        :param item: target word to be searched in HowNet
        :param language: specify the language of the target search word
        :return:(Boolean) whether the word exists in HowNet annotation
        """
        if language == "en":
            return item in self.en_map
        elif language == "zh":
            return item in self.zh_map

        return item in self.en_map or item in self.zh_map or item in self.sense_dic

    def get_all_sememes(self):
        """
        Get the complete sememe dict in HowNet
        :return: (Dict) a dict of sememes or (Dict) a dict of sememe and its frequency
        """
        return self.sememe_dic

    def initialize_sememe_similarity_calculation(self):
        """
        Initialize the word similarity calculation via sememes.
        Implementation is contributed by Jun Yan, which is based on the paper :
        "Jiangming Liu, Jinan Xu, Yujie Zhang. An Approach of Hybrid Hierarchical Structure for Word Similarity Computing by HowNet. In Proceedings of IJCNLP"
        :return: (Boolean) whether the initialization succeed.
        """
        pickle_prefix = os.sep.join(['pack', 'submit_user', 'pickle'])
        sememe_root_pickle_path = 'sememe_root.pkl'
        hownet_pickle_path = 'hownet.pkl'
        sememe_sim_table_pickle_path = 'sememe_sim_table.pkl'

        package_directory = os.path.dirname(os.path.abspath(__file__))
        try:
            sys.modules["util"] = util
            self.sememe_root = pickle.load(
                open(os.path.join(package_directory, pickle_prefix, sememe_root_pickle_path), "rb"))
            self.hownet = pickle.load(
                open(os.path.join(package_directory, pickle_prefix, hownet_pickle_path), "rb"))
            self.sememe_sim_table = pickle.load(
                open(os.path.join(package_directory, pickle_prefix, sememe_sim_table_pickle_path), "rb"))
            del sys.modules["util"]
        except FileNotFoundError as e:
            print(
                "Enabling Word Similarity Calculation requires specific data files, please check the completeness of your download package.")
            print(e)
            return False
        return True

    def get_nearest_words_via_sememes(self, word, K=10):
        """
        Get the topK nearest words of the given word, the word similarity is calculated based on HowNet annotation.
        If the given word does not exist in HowNet annotations, this function will return an empty list.
        :param word: target word
        :param K: specify the number of the nearest words you want to retrieve.
        :return: (List) a list of the nearest K words.
                If the given word does not exist in HowNet annotations, this function will return an empty list.
                If the initialization method of word similarity calculation has not been called yet, it will also return an empty list and print corresponding error message.
        """
        res = list()
        if not hasattr(self, "hownet") or not hasattr(self, "sememe_sim_table") or not hasattr(self, "sememe_root"):
            print("Please initialize the similarity calculation firstly!")
            return res
        if self.hownet is None or self.sememe_sim_table is None or self.sememe_root is None:
            print("Please initialize the similarity calculation firstly!")
            return res
        if word not in self.hownet.word2idx:
            print(word + ' is not annotated in HowNet.')
            return res
        for i in self.hownet.word[self.hownet.word2idx[word]].sense_id:
            tree1 = self.hownet.sense[i].tree
            score = {}
            banned_id = self.hownet.word[self.hownet.sense[i].word_id].sense_id
            for j in range(3378, len(self.hownet.sense)):
                if j not in banned_id:
                    tree2 = self.hownet.sense[j].tree
                    sim = sense_similarity(
                        tree1, tree2, self.hownet, self.sememe_sim_table)
                    score[j] = sim
            result = sorted(score.items(), key=lambda x: x[1], reverse=True)
            topK = result[0:K]
            # line = str(i) + ', ' + self.hownet.sense[i].str + '\t\t'
            queryRes = dict()
            queryRes["id"] = i
            queryRes["word"] = self.hownet.sense[i].str
            queryRes["synset"] = list()
            for m in topK:
                #   line = line + str(m[0]) + ', ' + self.hownet.sense[m[0]].str + ', ' + str("%.2f" % m[1]) + '; '
                single_syn: Dict[str, Any] = {
                    "id": m[0], "word": self.hownet.sense[m[0]].str, "score": m[1]}
                queryRes["synset"].append(single_syn)
            # line = line
            # print(line)
            res.append(queryRes)
        return res

    def calculate_word_similarity(self, word0, word1):
        """
        calculate the word similarity between two words via sememes
        :param word0: target word #0
        :param word1: target word #1
        :return: (Float) the word similarity calculated via sememes.
                 If word0 or word1 does not exist in HowNet annotation, it will return 0.0
                If the initialization method of word similarity calculation has not been called yet, it will also return 0.0 and print corresponding error message.
        """
        res = 0.0
        if not hasattr(self, "hownet") or not hasattr(self, "sememe_sim_table") or not hasattr(self, "sememe_root"):
            print("Please initialize the similarity calculation firstly!")
            return res
        if self.hownet is None or self.sememe_sim_table is None or self.sememe_root is None:
            print("Please initialize the similarity calculation firstly!")
            return res
        if word0 not in self.hownet.word2idx:
            print(word0 + ' is not annotated in HowNet.')
            return res
        if word1 not in self.hownet.word2idx:
            print(word1 + ' is not annotated in HowNet.')
            return res
        return word_similarity(word0, word1, self.hownet, self.sememe_sim_table)

    def get_sememe_relation(self, x, y):
        """
        Show relationship between two sememes.
        :return: (String) a string represents the relation.
        """
        if not hasattr(self, "sememe_taxonomy"):
            self._load_taxonomy()

        return self.sememe_taxonomy.get((x, y), "none")

    def get_sememe_via_relation(self, x, relation):
        """
        Show all sememes that x has relation with.
        :return: (List) a string represents all related sememes.
        """
        if not hasattr(self, "sememe_dict"):
            self._load_taxonomy()

        return [x for x in self.sememe_dict.get((x, relation), [])]

    def get_related_sememes(self, x):
        """
        Show all sememes that x has any relation with.
        :param x: target sememe, you can use any language(en/zh).
        :return: (List) a list contains sememe triples.
        """
        if not hasattr(self, "sememe_dict"):
            self._load_taxonomy()

        return list(self.sememe_related.get(x, "none"))

    def _load_sememe_sense_dic(self):
        """
        Load sememe to sense dict from file
        """
        f = get_resource("sememe_sense_dic", "rb")

        self.sememe_sense_dic = pickle.load(f)

    def get_senses_by_sememe(self, x):
        """
        Get the senses labeled by sememe x.
        :param x: (str)Target sememe
        :return: the list of senses which contains No, ch_word and en_word.
        """
        if not hasattr(self, "sememe_sense_dic"):
            self._load_sememe_sense_dic()

        return self.sememe_sense_dic.get(x, [])
