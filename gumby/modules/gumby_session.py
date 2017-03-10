import logging
import time as timemod

from os import path
from sys import path as pythonpath

from gumby.experiments.community_launcher import *

# TODO(emilon): Fix this crap
pythonpath.append(path.abspath(path.join(path.dirname(__file__), '..', '..', '..', "./tribler")))

from Tribler.Core.Session import Session
from Tribler.Core.APIImplementation.LaunchManyCore import TriblerLaunchMany
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class CommunityLoader(object):

    """
    Object in charge of loading communities into Dispersy.
    """

    def __init__(self):
        self.community_launchers = {}

    def set_launcher(self, launcher):
        """
        Register a launcher to be launched by name.

        If a launcher for the same name already existed, it is overwritten.

        :type launcher: CommunityLauncher
        """
        assert isinstance(launcher, CommunityLauncher)

        if launcher.get_name() in self.community_launchers:
            logging.warning("Overriding CommunityLauncher %s", launcher.get_name())

        self.community_launchers[launcher.get_name()] = (launcher, False)

    def del_launcher(self, launcher):
        """
        Unregister a launcher

        :type launcher: CommunityLauncher
        """
        assert isinstance(launcher, CommunityLauncher)

        if launcher.get_name() in self.community_launchers:
            del self.community_launchers[launcher.get_name()]

    def load(self, dispersy, session):
        """
        Load all of the communities specified by the registered launchers into Dispersy.

        :type dispersy: Tribler.dispersy.dispersy.Dispersy
        :type session: Tribler.Core.Session.Session
        """
        remaining = [launcher for launcher, _ in self.community_launchers.values()]
        cycle = len(remaining)*len(remaining)
        while remaining and cycle >= 0:
            launcher = remaining.pop(0)
            cycle -= 1
            if launcher.should_launch(session):
                validated = True
                for dependency in launcher.not_before():
                    # If the dependency does not exist, don't wait for it
                    # If the dependency is never loaded, don't wait for it
                    if dependency in self.community_launchers and \
                            self.community_launchers[dependency][0].should_launch(session):
                        _, loaded = self.community_launchers[dependency]
                        validated = validated and loaded
                if validated:
                    self._launch(launcher, dispersy, session)
                else:
                    remaining.append(launcher)
        if cycle < 0:
            launcher_names = [launcher.get_name() for launcher in remaining]
            raise RuntimeError("Cycle detected in CommunityLauncher not_before(): %s" % (str(launcher_names)))

    def _launch(self, launcher, dispersy, session):
        """
        Launch a launcher: register the community with Dispersy.
        """
        # Prepare launcher
        launcher.prepare(dispersy, session)
        # Register community
        community_class = launcher.get_community_class()
        member = launcher.get_my_member(dispersy, session)
        load_now = launcher.should_load_now(session)
        args = launcher.get_args(session)
        kwargs = launcher.get_kwargs(session)
        communities = dispersy.define_auto_load(community_class, member, args, kwargs, load_now)
        # Cleanup
        launcher.finalize(dispersy, session, communities[0] if communities else None)
        self.community_launchers[launcher.get_name()] = (launcher, True)


class DefaultCommunityLoader(CommunityLoader):

    """
    DefaultCommunityLoader, mimicking TriblerLaunchMany.
    """

    def __init__(self):
        super(DefaultCommunityLoader, self).__init__()
        self.set_launcher(SearchCommunityLauncher())
        self.set_launcher(AllChannelCommunityLauncher())
        self.set_launcher(ChannelCommunityLauncher())
        self.set_launcher(PreviewChannelCommunityLauncher())
        self.set_launcher(MultiChainCommunityLauncher())
        self.set_launcher(HiddenTunnelCommunityLauncher())


class GumbyLaunchMany(TriblerLaunchMany):

    """
    Overwritten TriblerLaunchMany allowing for custom community loading.
    """

    def __init__(self, community_loader=DefaultCommunityLoader()):
        super(GumbyLaunchMany, self).__init__()
        self.community_loader = community_loader

    @blocking_call_on_reactor_thread
    def load_communities(self):
        self._logger.info("tribler: Preparing communities...")
        now_time = timemod.time()

        self.community_loader.load(self.dispersy, self.session)

        self.session.set_anon_proxy_settings(2, ("127.0.0.1", self.session.get_tunnel_community_socks5_listen_ports()))

        self._logger.info("tribler: communities are ready in %.2f seconds", timemod.time() - now_time)


class GumbySession(Session):

    """
    Overwritten Session allowing for custom community loading in Session.lm.
    """

    def __init__(self, scfg=None, ignore_singleton=False, autoload_discovery=True):
        super(GumbySession, self).__init__(scfg, ignore_singleton, autoload_discovery)
        self.lm = GumbyLaunchMany()
