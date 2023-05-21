from queue import Queue, Empty
from tkinter import Button, Radiobutton, Label, LabelFrame, Frame, StringVar, W, EW, NSEW, NORMAL, DISABLED, Toplevel
from tkinter import Entry, Checkbutton, IntVar
from tkinter import messagebox
from tkinter.ttk import Treeview, Separator

from marytreat.core.constants import Constants
from marytreat.core.mary_debug import logger
from marytreat.core.mary_xml import XMLContent
from marytreat.core.threaded import ThreadedRepositorySearch, ThreadedMigrationCompletion, ThreadedMetadataDuplicator
from marytreat.core.threaded import ThreadedTitleAndDescriptionChecker, ThreadedTagDownload, ThreadedSubmapGenerator
from marytreat.core.tridionclient import SearchRepository, Project, Tag, Topic, Map
from marytreat.ui.utils import MaryProgressBar, get_icon, validate

padding = Constants.PADDING.value

EMPTY_BOX = '\u2610 '
CHECKED_BOX = '\u2611 '
BLUE_SQUARE = '\U0001F7E6 '
STRIPED_SQUARE = '\u9636 '


class NarrowDownLocation(LabelFrame):

    def __init__(self, master):
        super().__init__(master, text='Search in press series or DFE')
        self.part_type = StringVar()

        buttons = ['3', '4', '5', '6', 'Common in Presses', 'DFE']
        for button in buttons:
            btn = Radiobutton(self, text=button, variable=self.part_type, value=button.lower(),
                              command=self.call_get_location_folder)
            btn.grid(row=0, column=buttons.index(button), sticky=EW, **padding)
        self.part_type.set('common in presses')

        self.q = Queue()
        self.pb = MaryProgressBar()

    def call_get_location_folder(self):
        self.after(100, self.get_location_folder)

    def get_location_folder(self):
        part_type = self.part_type.get()
        logger.debug('part type: ' + part_type)
        if part_type:
            folder = SearchRepository.get_location(part_type)
            return folder


class SearchPartNumber(Frame):

    def __init__(self, master):
        super().__init__(master)
        self.search_query = StringVar()
        self.p_name = StringVar()
        self.p_id = StringVar()

        self.q = Queue()
        self.pb = MaryProgressBar()

        description = Label(self, text='Search project by part number:', anchor=W)
        description.grid(row=0, column=0, sticky=EW)

        query_field = Entry(self, textvariable=self.search_query)
        query_field.grid(row=1, column=0, columnspan=4, **padding, sticky=EW)

        search_button = Button(self, text='Search',
                               command=self.find_project)
        search_button.grid(row=1, column=3, **padding, sticky=EW)

        self.select_part_type = NarrowDownLocation(self)
        self.select_part_type.grid(row=2, column=0, columnspan=4, **padding, sticky=EW)

    def find_project(self):
        folder = self.select_part_type.get_location_folder()

        part_no = self.search_query.get()
        logger.debug('search query: ' + part_no)
        if folder and part_no:
            self.pb.start()
            t = ThreadedRepositorySearch(part_no, folder, self.q)
            t.start()
            self.after(300, self.check_queue_for_search_result)
        else:
            messagebox.showinfo('No project', 'Please type a part number in the search box.')

    def check_queue_for_search_result(self):
        try:
            result = self.q.get_nowait()
            if result and result != -1:
                self.p_name.set(result[0])
                self.p_id.set(result[1])
                self.pb.stopandhide()
                messagebox.showinfo('Found project', 'Found ' + result[0] + '.')
            else:
                self.pb.stopandhide()
                messagebox.showinfo('Not found', 'Project not found. Try a different scope.')
        except Empty:
            self.after(100, self.check_queue_for_search_result)
        except Exception as e:
            self.pb.stopandhide()
            self.q.put(-1)
            logger.error(e)


class ServerActionsTab(Frame):

    def __init__(self, master):
        super().__init__(master)
        self.project = None

        self.q = Queue()
        self.pb = MaryProgressBar()

        search = SearchPartNumber(self)
        search.grid(row=0, column=0, columnspan=3, sticky=EW)

        button_cheetah_migration = Button(self, text='Complete project migration',
                                          command=self.call_complete_migration, state=DISABLED)
        button_cheetah_migration.grid(row=1, column=0, **padding, sticky=EW)

        button_check_titles_and_sd = Button(self, text='Check titles and shortdescs',
                                            command=self.call_check_titles_and_sd, state=DISABLED)
        button_check_titles_and_sd.grid(row=1, column=1, **padding, sticky=EW)

        button_manage_pub = Button(self, text='Manage publication...',
                                   command=self.call_manage_pub, state=DISABLED)  # submaps; mark for tagging
        button_manage_pub.grid(row=1, column=2, **padding, sticky=EW)

        Separator(self, orient='horizontal').grid(row=2, column=0, columnspan=3, sticky=EW)

        # Project-independent actions, don't require a search for the project

        button_download_tag_values = Button(self, text='Download TMS values...',
                                            command=lambda: DownloadTagValueWindow())
        button_download_tag_values.grid(row=3, column=0, **padding, sticky=EW)

        button_copy_tags = Button(self, text='Copy tags from object...',
                                  command=lambda: CopyTagsWindow())
        button_copy_tags.grid(row=3, column=1, **padding, sticky=EW)

        button_wrap_in_map = Button(self, text='Wrap topic in map...',
                                    command=lambda: WrapInMapWindow())
        button_wrap_in_map.grid(row=3, column=2, **padding, sticky=EW)

        self.buttons = [
            button_cheetah_migration,
            button_check_titles_and_sd,
            # button_manage_pub
        ]

        self.name_entry = search.p_name
        self.id_entry = search.p_id
        self.name_entry.trace('w', self.turn_on_buttons)
        self.id_entry.trace('w', self.turn_on_buttons)

    def turn_on_buttons(self, *args):
        if self.name_entry.get() and self.id_entry.get():
            self.project = Project(name=self.name_entry.get(), id=self.id_entry.get())
            for button in self.buttons:
                button.configure(state=NORMAL)

    def call_complete_migration(self):
        if self.project:
            self.pb.start()
            t = ThreadedMigrationCompletion(self.project, self.q)
            t.start()
            self.after(300, self.check_queue_for_migration_completion)
        else:
            messagebox.showinfo('No project', 'Please select a project using the search box.')

    def check_queue_for_migration_completion(self):
        try:
            result = self.q.get_nowait()
            if result and result != -1:
                self.pb.stopandhide()
                messagebox.showinfo('Done', 'Migration completed.')
        except Empty:
            self.after(100, self.check_queue_for_migration_completion)
        except Exception as e:
            self.pb.stopandhide()
            self.q.put(-1)
            logger.error(e)

    def call_check_titles_and_sd(self):
        if self.project:
            self.pb.start()
            t = ThreadedTitleAndDescriptionChecker(self.project, self.q)
            t.start()
            self.after(500, self.check_queue_for_titles_and_shortdescs)
        else:
            messagebox.showinfo('No project', 'Please select a project using the search box.')

    def check_queue_for_titles_and_shortdescs(self):
        try:
            message = self.q.get_nowait()
            if message and message != -1:
                self.pb.stopandhide()
                messagebox.showinfo('Titles and shortdescs', message)
        except Empty:
            self.after(100, self.check_queue_for_titles_and_shortdescs)
        except Exception as e:
            self.pb.stopandhide()
            self.q.put(-1)
            logger.error(e)

    def call_manage_pub(self):
        if self.project:
            manage_pub = ManagePublication(self.project)
        else:
            messagebox.showinfo('No project', 'Please select a project using the search.')


class ManagePublication(Toplevel):

    def __init__(self, project):
        super().__init__()
        self.title('Manage publication')
        self.project = project

        pub_tree = LabelFrame(self, text='Publication tree', height=200, width=400)
        pub_tree.grid(row=0, column=0, sticky=NSEW)

        tree_actions = LabelFrame(self, text='Actions', width=300)
        tree_actions.grid(row=0, column=1, sticky=NSEW)

        columns = ['type', 'structure']
        self.tree_widget = Treeview(
            pub_tree,
            columns=columns,
            padding='10 10',
            selectmode='extended',
            show='tree'
        )
        map_tree = self.get_map_tree()
        if not map_tree:
            logger.warning('The publication does not contain a root map.')
            messagebox.showwarning('No root map',
                                   'The publication does not contain a root map. ' +
                                   'Please complete project migration.')
            self.destroy()
        self.fill_tree(map_tree)

    def fill_tree(self, map_tree):
        top_context = map_tree.root.findall('topicref')
        if len(top_context) != 1:
            logger.warning('There is no root context topic.')
            messagebox.showwarning('No root context',
                                   'There is no root context topic. Check the project structure.')
            return

        def create_row():
            pass

    def get_map_tree(self):
        pub = self.project.get_publication()
        if pub:
            ditamap = pub.get_map()
            if ditamap:
                return XMLContent(ditamap.get_decoded_content_as_tree())
        logger.error('Failed to get root map')

    # Display publication tree with checkboxes
    # Allow adding tags to checked objects
    # Allow wrapping context topics in submaps (and then adding tags)


class DownloadTagValueWindow(Toplevel):

    def __init__(self):
        super().__init__()
        self.title('Download TMS values')
        self.iconbitmap(get_icon())

        self.get_css, self.get_product, self.get_hardware = IntVar(), IntVar(), IntVar()

        check_css = Checkbutton(self, text='Customer Support Stories', variable=self.get_css)
        check_product = Checkbutton(self, text='Product values', variable=self.get_product)
        check_hardware = Checkbutton(self, text='Hardware values', variable=self.get_hardware)

        check_css.grid(row=0, column=0, sticky=W)
        check_product.grid(row=1, column=0, sticky=W)
        check_hardware.grid(row=2, column=0, sticky=W)

        download_button = Button(self, text='Download', command=self.call_download_values)
        download_button.grid(row=4, column=0, **padding, sticky=EW)

        self.q = Queue()
        self.pb = MaryProgressBar()

    def call_download_values(self):
        if all(val == 0 for val in [self.get_css.get(), self.get_product.get(), self.get_hardware.get()]):
            messagebox.showinfo('Empty checkboxes', 'Please check at least one box.')
            return

        requested_values = []
        if self.get_css.get() == 1:
            requested_values.append(Tag('fhpicustomersupportstories'))
        if self.get_product.get() == 1:
            requested_values.append(Tag('fhpiproduct'))
        if self.get_hardware.get() == 1:
            requested_values.append(Tag('fhpihardwarecomponents'))

        self.pb.start()
        t = ThreadedTagDownload(requested_values, self.q)
        t.start()
        self.after(300, self.check_queue_if_values_downloaded)

    def check_queue_if_values_downloaded(self):
        try:
            file_list = self.q.get_nowait()
            if file_list and file_list != -1:
                self.pb.stopandhide()
                msg = 'Downloaded values to file(s):\n'
                for fl in file_list:
                    msg = msg + fl + '\n'
                messagebox.showinfo('Value tables downloaded', msg)
        except Empty:
            self.after(100, self.check_queue_if_values_downloaded)
        except Exception as e:
            self.pb.stopandhide()
            self.q.put(-1)
            logger.error(e)


class CopyTagsWindow(Toplevel):

    def __init__(self):
        super().__init__()
        self.title('Copy tags')
        self.iconbitmap(get_icon())

        self.tag_source = StringVar()
        self.tag_destination = StringVar()

        Label(self, text='Source object (from which to copy tags)').grid(row=0, column=0, **padding, sticky=W)
        Entry(self, textvariable=self.tag_source, width=70).grid(row=1, column=0, columnspan=3, **padding, sticky=EW)

        Label(self, text='Target object').grid(row=2, column=0, **padding, sticky=W)
        Entry(self, textvariable=self.tag_destination, width=70).grid(row=3, column=0, columnspan=3, **padding, sticky=EW)

        what_tags = LabelFrame(self, text='Tags to copy')
        what_tags.grid(row=4, column=0, columnspan=3, **padding, sticky=W)

        self.copy_css = IntVar()
        self.copy_product = IntVar()
        # self.copy_hardware = IntVar()

        check_css = Checkbutton(what_tags, text='Customer Support Stories', variable=self.copy_css)
        check_product = Checkbutton(what_tags, text='Product values', variable=self.copy_product)
        # check_hardware = Checkbutton(what_tags, text='Hardware values', variable=self.get_hardware)

        check_css.grid(row=0, column=0, sticky=W)
        check_product.grid(row=1, column=0, sticky=W)
        # check_hardware.grid(row=2, column=0, sticky=W)

        Button(self, text='Copy', command=self.call_copy_tags).grid(
            row=5, column=0, columnspan=3, **padding, sticky=EW)

        self.q = Queue()
        self.pb = MaryProgressBar()

    def call_copy_tags(self):
        if all(val == 0 for val in [self.copy_css.get(), self.copy_product.get()]):
            messagebox.showinfo('Empty checkboxes', 'Please check at least one box.')
            return
        if not self.tag_destination.get() or not self.tag_source.get():
            messagebox.showinfo('No objects', 'Please specify both the tag source and destination.')
            return

        src_id = validate(self.tag_source.get())
        if src_id == -1:
            messagebox.showinfo('Object not found', 'Please enter a valid GUID of the source object. '
                                'Alternatively, Ctrl-C & Ctrl-V the object from Publication Manager.')
            return

        dest_id = validate(self.tag_destination.get())
        if dest_id == -1:
            messagebox.showinfo('Object not found', 'Please enter a valid GUID of the target object. '
                                'Alternatively, Ctrl-C & Ctrl-V the object from Publication Manager.')
            return

        self.pb.start()
        t = ThreadedMetadataDuplicator(src_id,
                                       dest_id,
                                       self.q,
                                       copy_product=self.copy_product.get(),
                                       copy_css=self.copy_css.get())
        t.start()
        self.after(300, self.check_queue_if_copied_tags)

    def check_queue_if_copied_tags(self):
        try:
            source_and_dest = self.q.get_nowait()
            if source_and_dest and source_and_dest != -1:
                self.pb.stopandhide()
                msg = 'Tags copied from {} to {}.'.format(str(source_and_dest[0]), str(source_and_dest[1]))
                messagebox.showinfo('Success', msg)
        except Empty:
            self.after(100, self.check_queue_if_copied_tags)
        except Exception as e:
            self.pb.stopandhide()
            self.q.put(-1)
            logger.error(e)


class WrapInMapWindow(Toplevel):

    def __init__(self):
        super().__init__()
        self.title('Wrap topic in map')
        self.iconbitmap(get_icon())

        self.q = Queue()
        self.pb = MaryProgressBar()

        self.context_topic = StringVar()
        self.root_map = StringVar()

        Label(self, text='Target context topic').grid(row=0, column=0, sticky=W)
        Entry(self, textvariable=self.context_topic, width=70).grid(row=1, column=0, columnspan=2, **padding, sticky=EW)

        Label(self, text='Root map').grid(row=2, column=0, sticky=W)
        Entry(self, textvariable=self.root_map, width=70).grid(row=3, column=0, columnspan=2, **padding, sticky=EW)

        Label(self, text='Please make sure that your root map is checked in.').grid(row=4, column=0, columnspan=2,
                                                                                    **padding, sticky=W)

        Button(self, text='Go', command=self.call_wrap_in_map).grid(
            row=5, column=0, **padding, sticky=EW)

    def call_wrap_in_map(self):
        if not self.context_topic.get() or not self.root_map.get():
            messagebox.showinfo('No objects', 'Please specify the context topic and its root map.')
            return

        topic_id = validate(self.context_topic.get())
        map_id = validate(self.root_map.get())
        if topic_id == -1 or map_id == -1:
            messagebox.showinfo('Objects not found', 'Please enter valid GUIDs. ' +
                                'Alternatively, Ctrl-C & Ctrl-V an object from Publication Manager.')
            return

        self.pb.start()
        t = ThreadedSubmapGenerator(Topic(id=topic_id), Map(id=map_id), self.q)
        t.start()
        self.after(100, self.check_queue_if_wrapped_in_map)

    def check_queue_if_wrapped_in_map(self):
        try:
            submap = self.q.get_nowait()
            if submap and submap != -1:
                self.pb.stopandhide()
                msg = 'New map {} added to root map.'.format(str(submap))
                messagebox.showinfo('Success', msg)
        except Empty:
            self.after(100, self.check_queue_if_wrapped_in_map)
        except Exception as e:
            self.pb.stopandhide()
            self.q.put(-1)
            logger.error(e)
